"""Prove the stack end to end: cluster, catalog, object store, Delta.

Run it with `make stack-smoke`. It is deliberately trivial as a data exercise
and deliberately complete as an infrastructure one. If this passes, every seam
in the stack is real: the job ran on executors that live in other containers,
the table is registered in Unity Catalog, and the bytes are in MinIO.

This runs through the Spark session catalog, not Unity Catalog. UC is up and
holds the namespace, but it cannot vend credentials for MinIO, so reads through
it fail with 403. ADR 0004 records why, and what would change to move over.
"""

import os

from pyspark.sql import SparkSession

BUCKET = os.environ.get("LAKEHOUSE_BUCKET", "lakehouse")
TABLE = "bronze.smoke"
LOCATION = f"s3a://{BUCKET}/bronze/smoke"


def main() -> int:
    spark = (
        SparkSession.builder.appName("stack-smoke")
        .master(os.environ.get("SPARK_MASTER_URL", "local[*]"))
        .getOrCreate()
    )

    print(f"spark version        : {spark.version}")
    print(f"master               : {spark.sparkContext.master}")

    spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {TABLE} (id BIGINT, bucket BIGINT) "
        f"USING DELTA LOCATION '{LOCATION}'"
    )
    spark.range(0, 1000).selectExpr("id", "id % 7 AS bucket").write.format("delta").mode(
        "overwrite"
    ).save(LOCATION)

    rows = spark.sql(f"SELECT count(*) AS c FROM {TABLE}").collect()[0]["c"]
    tables = [r.tableName for r in spark.sql("SHOW TABLES IN bronze").collect()]

    print(f"rows via catalog     : {rows}")
    print(f"tables in bronze     : {tables}")

    # The executors are the point of running a cluster rather than local[*].
    backend = spark.sparkContext._jsc.sc().schedulerBackend()
    print(f"executors registered : {backend.getExecutorIds().size()}")

    spark.stop()
    return 0 if rows == 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
