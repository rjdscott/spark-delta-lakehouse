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
from pyspark.sql.window import Window

from .catalog import conformance, ensure_table, location
from .spec import Spec, load_all

UNKNOWN = "UNKNOWN"
# Distinct from UNKNOWN on purpose. A salary credit has no merchant because
# none applies; a debit with a blank category is a gap in the source. Collapsing
# both into one member makes "spend by category" answer a question nobody asked.
NOT_APPLICABLE = "NOT_APPLICABLE"
MERCHANT_TYPES = ("DEBIT",)


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
    """Every version, carrying its effective range through from silver, plus a
    member for transactions whose party cannot be resolved.

    A null foreign key in a fact is a hole every consumer has to remember to
    handle. A member is a hole the model handles once. These arise where a
    party was deleted, closing its timeline per ADR 0007, while transactions on
    its accounts continue.
    """
    unknown = spark.createDataFrame(
        [(UNKNOWN,) * 8],
        "party_id string, full_name string, address_line string, "
        "suburb string, state string, postcode string, risk_rating string, segment string",
    ).select(
        F.sha2(F.lit(UNKNOWN), 256).alias("party_sk"),
        "party_id",
        "full_name",
        "address_line",
        "suburb",
        "state",
        "postcode",
        "risk_rating",
        "segment",
        F.lit(True).alias("is_placeholder"),
        F.current_timestamp().alias("updated_at"),
        F.lit("1900-01-01 00:00:00").cast("timestamp").alias("effective_from"),
        F.lit("9999-12-31 23:59:59").cast("timestamp").alias("effective_to"),
        F.lit(True).alias("is_current"),
    )
    real = spark.table("silver.party").select(
        surrogate(spec, "effective_from").alias("party_sk"),
        "party_id",
        "full_name",
        "address_line",
        "suburb",
        "state",
        "postcode",
        "risk_rating",
        "segment",
        F.lit(False).alias("is_placeholder"),
        "updated_at",
        "effective_from",
        "effective_to",
        "is_current",
    )
    return real.unionByName(unknown)


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


def category_code(category, txn_type):
    """The category a transaction belongs to, including when it has none."""
    blank = category.isNull() | (category == "")
    return (
        F.when(~blank, category)
        .when(txn_type.isin(*MERCHANT_TYPES), F.lit(UNKNOWN))
        .otherwise(F.lit(NOT_APPLICABLE))
        .alias("merchant_category_code")
    )


def build_dim_merchant_category(spark: SparkSession, spec: Spec) -> DataFrame:
    """Includes a member for transactions carrying no category.

    Defect 6 leaves three percent of transactions without one. Dropping them
    loses real money; leaving the null propagates into every count that joins
    through this dimension. A member is the modelling answer.
    """
    codes = (
        spark.table("silver.transaction")
        .select(category_code(F.col("merchant_category"), F.col("txn_type")))
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
            category_code(F.col("t.merchant_category"), F.col("t.txn_type"))
            == F.col("c.merchant_category_code"),
            "left",
        )
    )

    return resolved.select(
        F.col("t.txn_id").alias("txn_id"),
        # A fact points at a member or it points at nothing. Nothing is not an
        # option that survives contact with a consumer.
        F.coalesce(F.col("p.party_sk"), F.sha2(F.lit(UNKNOWN), 256)).alias("party_sk"),
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


def build_fact_daily_balance(spark: SparkSession, spec: Spec) -> DataFrame:
    """A periodic snapshot: one row per account per day, transacting or not.

    The rows for quiet days are the entire point of this grain. A fact table
    that only records movement cannot answer "what was the balance on the 14th"
    without the consumer reconstructing a running total, which is the work this
    table exists to do once instead of in every query.

    Balances carry forward across quiet days, so the closing balance is a real
    cumulative position rather than the day's movement.
    """
    account = spark.table("gold.dim_account").select(
        "account_sk", "account_id", "open_date", "close_date"
    )
    lo, hi = spark.table("gold.dim_date").agg(F.min("full_date"), F.max("full_date")).first()

    # Expand each account into its own open days with sequence(), rather than
    # joining accounts to a date dimension on a range. A range condition is a
    # non-equi join, which Spark executes as a nested loop: it OOM-killed the
    # executors here (exit 137), and Spark recovering by re-running the stage
    # made it look like a transient shuffle failure rather than a plan problem.
    open_days = (
        account.withColumn(
            "_from", F.greatest(F.coalesce(F.col("open_date"), F.lit(lo)), F.lit(lo))
        )
        .withColumn(
            "_to",
            F.least(F.coalesce(F.date_sub(F.col("close_date"), 1), F.lit(hi)), F.lit(hi)),
        )
        .filter(F.col("_from") <= F.col("_to"))
        .withColumn("full_date", F.explode(F.sequence("_from", "_to")))
        .withColumn("date_key", F.date_format("full_date", "yyyyMMdd").cast("int"))
        .select("account_sk", "account_id", "date_key")
    )

    movements = (
        spark.table("silver.transaction")
        .groupBy("account_id", F.date_format("txn_ts", "yyyyMMdd").cast("int").alias("date_key"))
        .agg(
            # The OPENING carry belongs in movement, because the running
            # balance must start from it, and in nothing else: it is a ledger
            # position, not activity. Before this filter a home loan's first
            # "debit" was its entire principal (review-06 M-06).
            F.sum("amount").alias("movement"),
            F.sum(
                F.when(
                    (F.col("amount") < 0) & (F.col("txn_type") != "OPENING"), F.col("amount")
                ).otherwise(0)
            ).alias("debit_amount"),
            F.sum(
                F.when(
                    (F.col("amount") >= 0) & (F.col("txn_type") != "OPENING"), F.col("amount")
                ).otherwise(0)
            ).alias("credit_amount"),
            F.count(F.when(F.col("txn_type") != "OPENING", 1)).alias("txn_count"),
        )
    )

    # sum() of decimal(18,2) widens to decimal(28,2). MERGE cast that back
    # implicitly; an overwrite does not, and fails with
    # DELTA_FAILED_TO_MERGE_FIELDS naming the column twice and the types not at
    # all. Cast every measure back to what the spec declares.
    zero = F.lit(0).cast("decimal(18,2)")
    money = lambda column: F.coalesce(F.col(column), zero).cast("decimal(18,2)")  # noqa: E731
    daily = open_days.join(movements, on=["account_id", "date_key"], how="left").select(
        "account_sk",
        "account_id",
        "date_key",
        money("movement").alias("movement"),
        money("debit_amount").alias("debit_amount"),
        money("credit_amount").alias("credit_amount"),
        F.coalesce(F.col("txn_count"), F.lit(0)).cast("int").alias("txn_count"),
    )

    running = (
        Window.partitionBy("account_id")
        .orderBy("date_key")
        .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    )
    return (
        daily.withColumn("closing_balance", F.sum("movement").over(running).cast("decimal(18,2)"))
        .withColumn(
            "opening_balance",
            (F.col("closing_balance") - F.col("movement")).cast("decimal(18,2)"),
        )
        .withColumn("updated_at", F.current_timestamp())
        .select(
            "account_sk",
            "account_id",
            "date_key",
            "opening_balance",
            "movement",
            "closing_balance",
            "debit_amount",
            "credit_amount",
            "txn_count",
            "updated_at",
        )
    )


def build_fact_account_lifecycle(spark: SparkSession, spec: Spec) -> DataFrame:
    """An accumulating snapshot: one row per account, milestones filled in place.

    Unlike the other two grains, a row here is revisited. The row is created
    when the account opens and the same row is updated when it first transacts,
    when it last transacts, and when it closes. Nulls are not missing data,
    they are milestones that have not happened yet.
    """
    account = spark.table("gold.dim_account").filter(~F.col("is_inferred"))
    # Milestones measure activity, and the OPENING carry is not activity:
    # before this filter every account's first "transaction" was the window's
    # first day (review-06 M-06). lifetime_amount keeps the carry on purpose,
    # because it is a position, not a rate.
    real = F.col("txn_type") != "OPENING"
    activity = (
        spark.table("silver.transaction")
        .groupBy("account_id")
        .agg(
            F.min(F.when(real, F.to_date("txn_ts"))).alias("first_txn"),
            F.max(F.when(real, F.to_date("txn_ts"))).alias("last_txn"),
            F.count(F.when(real, 1)).cast("int").alias("txn_count"),
            F.sum("amount").alias("lifetime_amount"),
        )
    )

    key = F.date_format(F.col("_d"), "yyyyMMdd").cast("int")
    joined = account.join(activity, on="account_id", how="left")
    return (
        joined.withColumn("_d", F.col("open_date"))
        .withColumn("opened_date_key", key)
        .withColumn("_d", F.col("first_txn"))
        .withColumn("first_txn_date_key", key)
        .withColumn("_d", F.col("last_txn"))
        .withColumn("last_txn_date_key", key)
        .withColumn("_d", F.col("close_date"))
        .withColumn("closed_date_key", key)
        .select(
            "account_sk",
            "account_id",
            "opened_date_key",
            "first_txn_date_key",
            "last_txn_date_key",
            "closed_date_key",
            F.datediff(F.col("first_txn"), F.col("open_date")).alias("days_to_first_txn"),
            F.datediff(F.coalesce(F.col("close_date"), F.current_date()), F.col("open_date")).alias(
                "days_open"
            ),
            F.coalesce(F.col("txn_count"), F.lit(0)).cast("int").alias("txn_count"),
            F.coalesce(F.col("lifetime_amount"), F.lit(0).cast("decimal(18,2)"))
            .cast("decimal(18,2)")
            .alias("lifetime_amount"),
            F.col("status").alias("current_status"),
            F.current_timestamp().alias("updated_at"),
        )
    )


BUILDERS = {
    "gold_dim_party": build_dim_party,
    "gold_dim_account": build_dim_account,
    "gold_dim_merchant_category": build_dim_merchant_category,
    "gold_dim_date": build_dim_date,
    "gold_fact_transaction": build_fact_transaction,
    "gold_fact_daily_balance": build_fact_daily_balance,
    "gold_fact_account_lifecycle": build_fact_account_lifecycle,
}

# Facts rebuilt wholesale from silver. See build().
RECOMPUTED = ("gold_fact_transaction", "gold_fact_daily_balance")

# Dimensions before the fact, because the fact resolves against them.
ORDER = (
    "gold_dim_party",
    "gold_dim_account",
    "gold_dim_merchant_category",
    "gold_dim_date",
    "gold_fact_transaction",
    "gold_fact_daily_balance",
    "gold_fact_account_lifecycle",
)


def build(spark: SparkSession, spec: Spec) -> int:
    ensure_table(spark, spec)
    problems = conformance(spark, spec)
    if problems:
        raise RuntimeError(
            f"{spec.table} does not match its spec, refusing to build:\n  " + "\n  ".join(problems)
        )

    df = BUILDERS[spec.name](spark, spec)

    # A fact that is fully recomputed from silver is an overwrite, not a merge.
    # MERGE on a 288,000 row recompute means a join of the table against itself
    # plus a not-matched-by-source scan, which is a large shuffle for no
    # benefit: nothing is being preserved that the recompute does not produce.
    # It also OOM-killed executors, and Spark retrying the stage disguised a
    # plan problem as a transient shuffle failure.
    #
    # Dimensions still merge, because a surrogate key must survive a rebuild,
    # and so does the accumulating snapshot, whose whole point is that a row is
    # revisited rather than replaced.
    if spec.name in RECOMPUTED:
        df.write.format("delta").mode("overwrite").save(location(spec))
        return spark.table(spec.table).count()

    parts = [f"t.{k} = s.{k}" for k in spec.business_key]
    if spec.history_type == "scd2":
        parts.append("t.effective_from = s.effective_from")
    match = " AND ".join(parts)

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
