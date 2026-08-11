"""The claims gold makes, checked against the tables it wrote.

The one that matters is temporal correctness. Everything else here is
arithmetic; resolving a transaction to the dimension version current at the
moment it occurred is the thing SCD2 exists for, and the only way to see it is
to find a transaction whose party changed after it happened and confirm the
fact points at the older version.
"""

from pyspark.sql import functions as F

from lakehouse.catalog import session


def main() -> int:
    spark = session("verify-gold")
    fact = spark.table("gold.fact_transaction")
    ok = True

    rows = fact.count()
    keys = fact.select("txn_id").distinct().count()
    verdict = "OK" if rows == keys else "BROKEN"
    print(f"fact grain          : rows={rows:,} distinct txn_id={keys:,} {verdict}")
    ok &= rows == keys

    for column, table, target in (
        ("party_sk", "gold.dim_party", "party_sk"),
        ("account_sk", "gold.dim_account", "account_sk"),
        ("merchant_category_sk", "gold.dim_merchant_category", "merchant_category_sk"),
        ("date_key", "gold.dim_date", "date_key"),
    ):
        ok &= orphan_check(spark, fact, column, table, target)

    inferred = spark.table("gold.dim_account").filter("is_inferred").count()
    print(f"inferred members    : {inferred}")

    unknown = (
        spark.table("gold.dim_merchant_category")
        .filter("merchant_category_code = 'UNKNOWN'")
        .select(F.col("merchant_category_sk").alias("_k"))
    )
    via_unknown = (
        fact.select(F.col("merchant_category_sk").alias("_k"))
        .join(unknown, on="_k", how="semi")
        .count()
    )
    print(f"facts via UNKNOWN category: {via_unknown:,}")
    ok &= via_unknown > 0

    # Temporal correctness. Find transactions belonging to a party that has
    # more than one version, and confirm the fact resolved to the version whose
    # range contains txn_ts rather than the one that is current.
    versions = spark.table("gold.dim_party").groupBy("party_id").count().filter("count > 1")
    resolved = (
        fact.alias("f")
        .join(spark.table("gold.dim_party").alias("d"), F.col("f.party_sk") == F.col("d.party_sk"))
        .join(versions.alias("v"), F.col("d.party_id") == F.col("v.party_id"), "semi")
    )
    total = resolved.count()
    correct = resolved.filter(
        (F.col("f.txn_ts") >= F.col("d.effective_from"))
        & (F.col("f.txn_ts") < F.col("d.effective_to"))
    ).count()
    stale = resolved.filter(~F.col("d.is_current")).count()
    print(f"multi-version parties: facts={total:,} inside effective range={correct:,}")
    print(f"  of those, resolved to a NON-current version: {stale:,}")
    ok &= total == correct and stale > 0

    late = fact.filter(F.col("settlement_lag_days") >= 1).count()
    print(f"late-settling facts : {late:,}")
    ok &= late > 0

    ok &= check_daily_balance(spark)
    ok &= check_lifecycle(spark)

    spark.stop()
    return 0 if ok else 1


def orphan_check(spark, fact, column, table, target) -> bool:
    """Every non-null foreign key resolves in its dimension.

    Runs for every declared relationship on every fact. It was run for
    fact_transaction alone, and the fact tables it skipped were exactly
    where the orphans were (review-07 H-01).
    """
    # Aliases are not optional here: both sides carry the same column
    # name, and Spark refuses an ambiguous join key rather than guessing.
    dim = spark.table(table).select(F.col(target).alias("_k")).distinct()
    orphans = (
        fact.filter(F.col(column).isNotNull())
        .select(F.col(column).alias("_k"))
        .join(dim, on="_k", how="left_anti")
        .count()
    )
    nulls = fact.filter(F.col(column).isNull()).count()
    print(f"{column:22s} orphan keys={orphans:>6,}  null keys={nulls:>6,}")
    return orphans == 0


def check_daily_balance(spark) -> bool:
    """A periodic snapshot: every open day present, balances carrying forward."""
    bal = spark.table("gold.fact_daily_balance")
    ok = True
    print()

    rows = bal.count()
    keys = bal.select("account_id", "date_key").distinct().count()
    print(
        f"balance grain       : rows={rows:,} distinct account-days={keys:,} "
        f"{'OK' if rows == keys else 'BROKEN'}"
    )
    ok &= rows == keys

    # The rows for days with no transactions are the reason this grain exists.
    quiet = bal.filter("txn_count = 0").count()
    print(f"quiet days carried  : {quiet:,} of {rows:,}")
    ok &= quiet > 0

    ok &= orphan_check(spark, bal, "account_sk", "gold.dim_account", "account_sk")
    ok &= orphan_check(spark, bal, "date_key", "gold.dim_date", "date_key")

    # Reconcile against silver, the layer this fact is derived from. The old
    # checks here compared the fact to itself (opening = closing - movement is
    # true by construction) and could not fail; a dropped movement passed
    # every one of them (review-07 M-05). These can fail.
    silver_txn = spark.table("silver.transaction")
    truth = silver_txn.groupBy("account_id").agg(F.sum("amount").alias("truth"))
    total = bal.groupBy("account_id").agg(F.sum("movement").alias("total"))
    mismatched = (
        total.join(truth, on="account_id", how="full")
        .filter(
            F.abs(F.coalesce(F.col("total"), F.lit(0)) - F.coalesce(F.col("truth"), F.lit(0)))
            > 0.01
        )
        .count()
    )
    print(f"accounts where gold movement != silver amounts: {mismatched}")
    ok &= mismatched == 0

    gold_count = bal.agg(F.sum("txn_count")).first()[0]
    silver_count = silver_txn.filter("txn_type != 'OPENING'").count()
    verdict = "OK" if gold_count == silver_count else "BROKEN"
    print(
        f"txn_count total     : gold={gold_count:,} silver non-OPENING={silver_count:,} {verdict}"
    )
    ok &= gold_count == silver_count

    # No day may fall outside the account's life.
    account = spark.table("gold.dim_account").select("account_id", "open_date", "close_date")
    outside = (
        bal.join(account, on="account_id")
        .withColumn("_d", F.to_date(F.col("date_key").cast("string"), "yyyyMMdd"))
        .filter(
            (F.col("_d") < F.col("open_date"))
            | (F.col("close_date").isNotNull() & (F.col("_d") >= F.col("close_date")))
        )
        .count()
    )
    print(f"days outside life   : {outside}")
    ok &= outside == 0
    return ok


def check_lifecycle(spark) -> bool:
    """An accumulating snapshot: one row per account, milestones in order."""
    life = spark.table("gold.fact_account_lifecycle")
    ok = True
    print()

    rows = life.count()
    keys = life.select("account_id").distinct().count()
    print(
        f"lifecycle grain     : rows={rows:,} distinct accounts={keys:,} "
        f"{'OK' if rows == keys else 'BROKEN'}"
    )
    ok &= rows == keys

    out_of_order = life.filter(
        (F.col("first_txn_date_key") < F.col("opened_date_key"))
        | (F.col("last_txn_date_key") < F.col("first_txn_date_key"))
        | (
            F.col("closed_date_key").isNotNull()
            & (F.col("last_txn_date_key") > F.col("closed_date_key"))
        )
    ).count()
    print(f"milestones out of order: {out_of_order}")
    ok &= out_of_order == 0

    ok &= orphan_check(spark, life, "account_sk", "gold.dim_account", "account_sk")
    for column in ("opened_date_key", "first_txn_date_key", "last_txn_date_key", "closed_date_key"):
        ok &= orphan_check(spark, life, column, "gold.dim_date", "date_key")

    # A closure the data cannot have observed yet: the generator once stamped
    # CLOSED with close dates years past the last extract (review-07 H-02).
    horizon = spark.table("gold.fact_daily_balance").agg(F.max("date_key")).first()[0]
    future = life.filter(F.col("closed_date_key") > F.lit(horizon)).count()
    print(f"closed beyond data  : {future}")
    ok &= future == 0

    # Nulls here are milestones that have not happened, not missing data.
    never = life.filter("first_txn_date_key IS NULL").count()
    open_now = life.filter("closed_date_key IS NULL").count()
    print(f"never transacted    : {never:,}   still open: {open_now:,}")
    return ok


if __name__ == "__main__":
    raise SystemExit(main())
