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
        ok &= orphans == 0

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

    spark.stop()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
