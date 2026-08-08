"""Report bronze row counts per batch, and the grain the catalog is holding.

Run it twice around a reload to prove idempotency: a batch replaces itself
rather than appending, so the totals must not move.
"""

from lakehouse.catalog import session


def main() -> int:
    spark = session("verify-bronze")
    for table in ("party", "account", "transaction"):
        total = spark.sql(f"SELECT count(*) c FROM bronze.{table}").collect()[0]["c"]
        per_batch = spark.sql(
            f"SELECT _batch_id, count(*) c FROM bronze.{table} "
            "GROUP BY _batch_id ORDER BY _batch_id"
        ).collect()
        breakdown = "  ".join(f"{r._batch_id}={r.c:,}" for r in per_batch)
        print(f"bronze.{table:12s} total={total:>8,}   {breakdown}")

    grain = (
        spark.sql("DESCRIBE TABLE EXTENDED bronze.party").filter("col_name = 'Comment'").collect()
    )
    print(f"\nbronze.party grain from the catalog: {grain[0]['data_type'] if grain else 'MISSING'}")
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
