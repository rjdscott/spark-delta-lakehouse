"""Walk the whole lakehouse, one batch at a time, narrating as it goes.

This is the demo, and it is also the honest way to run the pipeline. Advancing
one batch at a time is what a daily run does, and it is the only way the seeded
defects mean anything: a late-arriving account is only late if the batches
arrive in order. Rebuilding everything from every batch at once makes the
timeline disappear and several of the defects with it.

Run it with `make demo` after `make stack-up`. It assumes the extracts are
already in the landing zone, which `make seed` puts there.
"""

from __future__ import annotations

import sys

from pyspark.sql import functions as F

from lakehouse import bronze, gold, scd2, silver
from lakehouse.catalog import session
from lakehouse.spec import load_all

BATCHES = ("2026-01-15", "2026-02-15", "2026-03-15")


def rule(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def snapshot(spark) -> None:
    """What the warehouse currently knows, after this batch."""
    accounts = spark.table("gold.dim_account")
    inferred = accounts.filter("is_inferred").count()
    party_versions = spark.table("gold.dim_party").count()
    current = spark.table("gold.dim_party").filter("is_current AND NOT is_placeholder").count()
    facts = spark.table("gold.fact_transaction").count()

    print(
        f"  dim_party {party_versions:>6,} versions ({current:,} current)   "
        f"dim_account {accounts.count():>6,} ({inferred} inferred)   "
        f"fact_transaction {facts:>7,}"
    )
    if inferred:
        example = accounts.filter("is_inferred").select("account_id").first()[0]
        print(
            f"  inferred member: {example} is referenced by transactions but its "
            "account record has not arrived yet"
        )


def main() -> int:
    spark = session("demo")
    specs = load_all()

    for index, batch in enumerate(BATCHES, start=1):
        rule(f"BATCH {index} of {len(BATCHES)}: {batch}")

        print("bronze: land the extracts as they arrived, every column a string")
        for spec in sorted(
            (s for s in specs.values() if s.layer == "bronze"), key=lambda s: s.name
        ):
            rows = bronze.load_batch(spark, spec, f"{bronze.STORAGE_ROOT}/landing", batch)
            print(f"  {spec.table:22s} {rows:>7,} rows")

        print("silver: type, deduplicate, conform. No dimensional resolution")
        for spec in sorted(
            (s for s in specs.values() if s.layer == "silver" and s.history_type == "scd1"),
            key=lambda s: s.name,
        ):
            print(f"  {spec.table:22s} {silver.build(spark, spec, batch):>7,} rows")

        print("silver: party as SCD2, rebuilding the timeline for touched keys")
        party = scd2.build(spark, specs["silver_party"], batch)
        print(
            f"  silver.party           {party['rows']:>7,} versions, "
            f"{party['current']:,} current, {party['closed_as_deleted']} closed as deleted"
        )

        print("gold: conformed dimensions, then facts resolved at event time")
        for name in gold.ORDER:
            print(f"  {specs[name].table:22s} {gold.build(spark, specs[name]):>7,} rows")

        snapshot(spark)

    rule("WHAT THE MODEL BOUGHT")

    versions = spark.table("gold.dim_party").groupBy("party_id").count().filter("count > 1")
    resolved = (
        spark.table("gold.fact_transaction")
        .alias("f")
        .join(spark.table("gold.dim_party").alias("d"), F.col("f.party_sk") == F.col("d.party_sk"))
        .join(versions.alias("v"), F.col("d.party_id") == F.col("v.party_id"), "semi")
    )
    stale = resolved.filter(~F.col("d.is_current")).count()
    print(
        f"{resolved.count():,} transactions belong to a party that changed.\n"
        f"{stale:,} of them resolved to a version that is NOT the current one,\n"
        "because they are joined to the version whose effective range contains\n"
        "txn_ts. A join to is_current would answer differently, and wrongly."
    )

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
