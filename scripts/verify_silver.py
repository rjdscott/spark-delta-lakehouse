"""Check the properties silver claims, against the tables it actually wrote.

Row counts prove nothing on their own. These are the claims: one row per
business key, types actually coerced, duplicates removed without collapsing
distinct versions, and orphan references counted rather than dropped.
"""

from pyspark.sql import functions as F

from lakehouse.catalog import session


def main() -> int:
    spark = session("verify-silver")
    ok = True

    for table, key in (("silver.account", "account_id"), ("silver.transaction", "txn_id")):
        rows = spark.table(table).count()
        keys = spark.table(table).select(key).distinct().count()
        grain = "OK" if rows == keys else "BROKEN"
        print(f"{table:20s} rows={rows:>7,}  distinct {key}={keys:>7,}  grain {grain}")
        ok &= rows == keys

    bronze_keys = spark.table("bronze.account").select("account_id").distinct().count()
    silver_keys = spark.table("silver.account").select("account_id").distinct().count()
    print(
        f"\ndedupe: bronze distinct accounts={bronze_keys:,} silver={silver_keys:,} "
        f"{'OK' if bronze_keys == silver_keys else 'LOST ROWS'}"
    )
    ok &= bronze_keys == silver_keys

    types = dict(spark.table("silver.transaction").dtypes)
    print(
        f"coercion: amount={types['amount']} "
        f"txn_ts={types['txn_ts']} posted_ts={types['posted_ts']}"
    )
    ok &= types["amount"].startswith("decimal") and types["txn_ts"] == "timestamp"

    # Defect 4: transactions referencing accounts that arrived in a later
    # batch. Silver counts them; it does not drop them and does not resolve
    # them, because resolution is gold's job.
    orphans = (
        spark.table("silver.transaction")
        .alias("t")
        .join(
            spark.table("silver.account").alias("a"),
            F.col("t.account_id") == F.col("a.account_id"),
            "left_anti",
        )
        .count()
    )
    print(f"orphan account references retained: {orphans:,}")

    # No dimensional resolution leaked into silver.
    leaked = [c for c in spark.table("silver.transaction").columns if c.endswith("_key")]
    verdict = "LEAKED" if leaked else "OK"
    print(f"surrogate keys in silver.transaction: {leaked or 'none'} {verdict}")
    ok &= not leaked

    spark.stop()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
