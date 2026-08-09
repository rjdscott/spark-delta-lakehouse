"""Gold: conformed dimensions and facts, built on silver.

Built on silver, never from bronze. That is the whole argument. If a dimension
here reached past silver to rebuild entity logic, the thesis this repo makes
would be false inside its own codebase.

**Surrogate keys are hashes, not identity columns.** A hash of the business key
plus, where the entity keeps history, the version's `effective_from`. Identity
columns depend on insertion order, so rebuilding the warehouse renumbers every
row and every fact table breaks. A hash gives the same input the same key
forever, on any machine, which is what makes a rebuild safe and an environment
comparable.

**Facts resolve at event time.** `fact_transaction` joins to the party version
whose effective range contains `txn_ts`, not the version current now and not
the one current when the row loaded. Defect 5 posts transactions up to five
days after they occur precisely so that a lazy join to `is_current` gives a
visibly different answer.

**Orphan references become inferred members.** Defect 4 lets transactions
reference accounts that arrive in a later batch. The transactions are real and
cannot be dropped, and the dimension member does not exist yet, so a
placeholder is created, flagged, and replaced when the real record arrives.
"""

from __future__ import annotations

import argparse
import json

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .catalog import conformance, ensure_table
from .spec import Spec, load_all

UNKNOWN = "UNKNOWN"


def surrogate(spec: Spec, *extra: str):
    """Hash of the business key, plus the version start where history is kept.

    sha2 rather than Spark's `hash`: 64 bits of murmur across millions of rows
    is a collision waiting to be someone else's outage, and the width costs
    nothing at this scale.
    """
    parts = [F.coalesce(F.col(k).cast("string"), F.lit(UNKNOWN)) for k in spec.business_key]
    parts += [F.coalesce(F.col(c).cast("string"), F.lit(UNKNOWN)) for c in extra]
    # Unit separator so ("ab", "c") and ("a", "bc") cannot hash alike.
    # An escape, not a literal control byte: those make the file
    # unimportable and neither ruff nor grep reliably flags them.
    return F.sha2(F.concat_ws("\u001f", *parts), 256)


def build_dim_party(spark: SparkSession, spec: Spec) -> DataFrame:
    """Every version, carrying its effective range through from silver."""
    return spark.table("silver.party").select(
        surrogate(spec, "effective_from").alias("party_sk"),
        "party_id",
        "full_name",
        "address_line",
        "suburb",
        "state",
        "postcode",
        "risk_rating",
        "segment",
        "updated_at",
        "effective_from",
        "effective_to",
        "is_current",
    )


def build_dim_account(spark: SparkSession, spec: Spec) -> DataFrame:
    """Real accounts, plus an inferred member for every account a transaction
    references that silver has not seen yet."""
    real = spark.table("silver.account").select(
        surrogate(spec).alias("account_sk"),
        "account_id",
        "party_id",
        "product_type",
        "open_date",
        "close_date",
        "status",
        F.lit(False).alias("is_inferred"),
        "updated_at",
    )

    orphans = (
        spark.table("silver.transaction")
        .select("account_id")
        .distinct()
        .join(spark.table("silver.account").select("account_id"), on="account_id", how="left_anti")
    )
    inferred = orphans.select(
        surrogate(spec).alias("account_sk"),
        "account_id",
        F.lit(None).cast("string").alias("party_id"),
        F.lit(UNKNOWN).alias("product_type"),
        F.lit(None).cast("date").alias("open_date"),
        F.lit(None).cast("date").alias("close_date"),
        F.lit(UNKNOWN).alias("status"),
        F.lit(True).alias("is_inferred"),
        F.current_timestamp().alias("updated_at"),
    )
    return real.unionByName(inferred)


def build_dim_merchant_category(spark: SparkSession, spec: Spec) -> DataFrame:
    """Includes a member for transactions carrying no category.

    Defect 6 leaves three percent of transactions without one. Dropping them
    loses real money; leaving the null propagates into every count that joins
    through this dimension. A member is the modelling answer.
    """
    codes = (
        spark.table("silver.transaction")
        .select(
            F.when(
                F.col("merchant_category").isNull() | (F.col("merchant_category") == ""),
                F.lit(UNKNOWN),
            )
            .otherwise(F.col("merchant_category"))
            .alias("merchant_category_code")
        )
        .distinct()
    )
    return codes.select(
        surrogate(spec).alias("merchant_category_sk"),
        "merchant_category_code",
        F.initcap(F.regexp_replace(F.col("merchant_category_code"), "_", " ")).alias(
            "merchant_category_name"
        ),
        F.current_timestamp().alias("updated_at"),
    )


def build_dim_date(spark: SparkSession, spec: Spec) -> DataFrame:
    bounds = spark.table("silver.transaction").agg(
        F.min(F.to_date("txn_ts")).alias("lo"), F.max(F.to_date("posted_ts")).alias("hi")
    )
    days = bounds.select(F.explode(F.sequence("lo", "hi")).alias("full_date"))
    return days.select(
        F.date_format("full_date", "yyyyMMdd").cast("int").alias("date_key"),
        "full_date",
        F.dayofmonth("full_date").alias("day_of_month"),
        F.month("full_date").alias("month_number"),
        F.date_format("full_date", "MMMM").alias("month_name"),
        F.quarter("full_date").alias("quarter"),
        F.year("full_date").alias("year_number"),
        F.dayofweek("full_date").isin(1, 7).alias("is_weekend"),
        F.current_timestamp().alias("updated_at"),
    )


def build_fact_transaction(spark: SparkSession, spec: Spec) -> DataFrame:
    """Resolve each transaction to the dimension versions current at txn_ts.

    The party join is an as-of join on the effective range, not a join to
    `is_current`. A transaction from January must resolve to the party as they
    were in January, even though the pipeline is running in March and even
    though the transaction settled in February.
    """
    txn = spark.table("silver.transaction")
    party = spark.table("gold.dim_party").select(
        "party_sk", "party_id", "effective_from", "effective_to"
    )
    account = spark.table("gold.dim_account").select("account_sk", "account_id", "party_id")
    category = spark.table("gold.dim_merchant_category").select(
        "merchant_category_sk", "merchant_category_code"
    )

    resolved = (
        txn.alias("t")
        .join(account.alias("a"), F.col("t.account_id") == F.col("a.account_id"), "left")
        # The as-of join. Half-open range, so a transaction at the exact instant
        # of a change belongs to the new version.
        .join(
            party.alias("p"),
            (F.col("a.party_id") == F.col("p.party_id"))
            & (F.col("t.txn_ts") >= F.col("p.effective_from"))
            & (F.col("t.txn_ts") < F.col("p.effective_to")),
            "left",
        )
        .join(
            category.alias("c"),
            F.coalesce(
                F.when(F.col("t.merchant_category") == "", None).otherwise(
                    F.col("t.merchant_category")
                ),
                F.lit(UNKNOWN),
            )
            == F.col("c.merchant_category_code"),
            "left",
        )
    )

    return resolved.select(
        F.col("t.txn_id").alias("txn_id"),
        F.col("p.party_sk").alias("party_sk"),
        F.col("a.account_sk").alias("account_sk"),
        F.col("c.merchant_category_sk").alias("merchant_category_sk"),
        F.date_format(F.col("t.txn_ts"), "yyyyMMdd").cast("int").alias("date_key"),
        F.col("t.txn_ts").alias("txn_ts"),
        F.col("t.posted_ts").alias("posted_ts"),
        F.datediff(F.col("t.posted_ts"), F.col("t.txn_ts")).alias("settlement_lag_days"),
        F.col("t.amount").alias("amount"),
        F.col("t.currency").alias("currency"),
        F.col("t.txn_type").alias("txn_type"),
    )


BUILDERS = {
    "gold_dim_party": build_dim_party,
    "gold_dim_account": build_dim_account,
    "gold_dim_merchant_category": build_dim_merchant_category,
    "gold_dim_date": build_dim_date,
    "gold_fact_transaction": build_fact_transaction,
}

# Dimensions before the fact, because the fact resolves against them.
ORDER = (
    "gold_dim_party",
    "gold_dim_account",
    "gold_dim_merchant_category",
    "gold_dim_date",
    "gold_fact_transaction",
)


def build(spark: SparkSession, spec: Spec) -> int:
    ensure_table(spark, spec)
    problems = conformance(spark, spec)
    if problems:
        raise RuntimeError(
            f"{spec.table} does not match its spec, refusing to build:\n  " + "\n  ".join(problems)
        )

    df = BUILDERS[spec.name](spark, spec)
    key = spec.business_key[0]
    match = f"t.{key} = s.{key}"
    if spec.history_type == "scd2":
        match += " AND t.effective_from = s.effective_from"

    target = DeltaTable.forName(spark, spec.table)
    (
        target.alias("t")
        .merge(df.alias("s"), match)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .whenNotMatchedBySourceDelete()
        .execute()
    )
    return spark.table(spec.table).count()


def main(argv: list[str] | None = None) -> int:
    from .catalog import session

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", help="one gold table, default all in dependency order")
    args = parser.parse_args(argv)

    spark = session("gold")
    specs = load_all()
    names = [args.table] if args.table else list(ORDER)
    counts = {specs[n].table: build(spark, specs[n]) for n in names}
    print(json.dumps({"rows": counts}, indent=2))
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
