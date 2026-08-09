"""The one module that knows which catalog and which storage root are in play.

Everything else names a table (`bronze.party`) and never a path or a scheme.
That is the seam: moving from the Hive Metastore to Unity Catalog, or from
MinIO to real S3, should touch this file and nothing else. ADR 0004 and
ADR 0005 record why the catalog is what it is today.
"""

from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession

from .ddl import columns, create_database, create_table
from .spec import Spec

STORAGE_ROOT = os.environ.get("STORAGE_ROOT", "s3a://lakehouse")


def session(app_name: str) -> SparkSession:
    """Configuration lives in spark-defaults.conf, baked into the image, so
    driver and executors cannot disagree. Nothing is set here."""
    builder = SparkSession.builder.appName(app_name)
    master = os.environ.get("SPARK_MASTER_URL")
    if master:
        builder = builder.master(master)
    return builder.getOrCreate()


def location(spec: Spec) -> str:
    return f"{STORAGE_ROOT}/{spec.layer}/{spec.name.removeprefix(spec.layer + '_')}"


def ensure_table(spark: SparkSession, spec: Spec) -> str:
    """Create the database and table from the spec if they do not exist.

    Returns the table name so callers read it from here rather than
    reconstructing it.
    """
    spark.sql(create_database(spec.layer))
    spark.sql(create_table(spec, location(spec)))
    return spec.table


def conformance(spark: SparkSession, spec: Spec) -> list[str]:
    """Differences between the declared spec and the physical table.

    This is what makes the spec load bearing rather than decorative. DDL is
    `CREATE TABLE IF NOT EXISTS`, so editing a spec after a table exists
    changes nothing and warns nobody; without this check the tables are derived
    exactly once and drift freely afterwards.

    Returns an empty list when the table matches.
    """
    problems: list[str] = []
    actual = {f.name: f.dataType.simpleString() for f in spark.table(spec.table).schema.fields}

    for name, declared, _ in columns(spec):
        if name not in actual:
            problems.append(f"{spec.table}: declared column '{name}' is missing")
            continue
        # Spark reports decimal(18,2) as decimal(18,2) and string as string, so
        # a normalised comparison is enough; anything subtler than this wants
        # a real type model, which the spec deliberately does not have.
        if actual[name].replace(" ", "") != declared.replace(" ", ""):
            problems.append(f"{spec.table}.{name}: declared {declared}, table has {actual[name]}")

    for name in actual:
        if name not in {c[0] for c in columns(spec)}:
            problems.append(f"{spec.table}: table has undeclared column '{name}'")

    properties = dict(
        spark.sql(f"SHOW TBLPROPERTIES {spec.table}").rdd.map(lambda r: (r[0], r[1])).collect()
    )
    if properties.get("lakehouse.grain") != spec.grain:
        problems.append(f"{spec.table}: grain in the table does not match the spec")

    return problems


def write_append(df: DataFrame, spec: Spec) -> None:
    df.write.format("delta").mode("append").save(location(spec))
