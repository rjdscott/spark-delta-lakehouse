"""Bronze: land the extracts as they arrived, and nothing else.

Append-only, source-shaped, every column a string. No dedupe, no renaming, no
type coercion, no business logic. If a value is malformed, bronze's job is to
keep it, not to reject it: the record is evidence of what the source actually
sent, and a pipeline that refuses it has destroyed the only copy.

Three columns are added, and they are lineage rather than business data:
`_ingest_ts`, `_source_file` and `_batch_id`. Unexpected columns in the
extract are captured in `_rescued_data` rather than dropped, so a source that
silently adds a field does not silently lose it.

Idempotency is by batch: re-running a batch replaces that batch's rows rather
than appending them again, so the layer converges instead of growing.
"""

from __future__ import annotations

import argparse
import json

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from .catalog import STORAGE_ROOT, conformance, ensure_table, location
from .spec import Spec, load_all

RESCUED_COLUMN = "_rescued_data"


def read_extract(spark: SparkSession, spec: Spec, path: str, batch_id: str) -> DataFrame:
    """Read the CSV as text, then attach lineage.

    Everything is read as a string on purpose. Letting Spark infer types here
    would make bronze the layer that decides what a value means, which is
    silver's job, and would turn a malformed value into a null with no record
    that it was ever different.
    """
    declared = [a.name for a in spec.attributes]
    schema = StructType([StructField(name, StringType(), True) for name in declared])

    raw = spark.read.csv(path, header=True, schema=schema, columnNameOfCorruptRecord=None)

    # Columns the source sent that the spec does not declare. Reading with an
    # explicit schema drops them silently, so read the header separately and
    # capture the difference rather than pretending it did not happen.
    header = spark.read.csv(path, header=True, inferSchema=False).columns
    unexpected = [c for c in header if c not in declared]
    if unexpected:
        wide = spark.read.csv(path, header=True, inferSchema=False)
        rescued = F.to_json(F.struct(*[F.col(c) for c in unexpected]))
        raw = wide.select(*[F.col(c).cast("string").alias(c) for c in declared]).withColumn(
            RESCUED_COLUMN, rescued
        )
    else:
        raw = raw.withColumn(RESCUED_COLUMN, F.lit(None).cast("string"))

    return (
        raw.withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.lit(path))
        .withColumn("_batch_id", F.lit(batch_id))
    )


def load_batch(spark: SparkSession, spec: Spec, root: str, batch_id: str) -> int:
    """Land one batch for one entity. Idempotent: the batch replaces itself."""
    path = f"{root}/{batch_id}/{spec.source_file}.csv"
    ensure_table(spark, spec)

    problems = conformance(spark, spec)
    if problems:
        raise RuntimeError(
            f"{spec.table} does not match its spec, refusing to load:\n  " + "\n  ".join(problems)
        )

    df = read_extract(spark, spec, path, batch_id)
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("replaceWhere", f"_batch_id = '{batch_id}'")
        .save(location(spec))
    )
    return df.count()


def main(argv: list[str] | None = None) -> int:
    from .catalog import session

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="batch date, e.g. 2026-01-15")
    # The landing zone is object storage, not a container filesystem. A local
    # path only works if every executor can see it, which in a real cluster
    # means an NFS mount nobody wants to operate.
    parser.add_argument("--root", default=f"{STORAGE_ROOT}/landing")
    parser.add_argument("--entity", help="one entity, default all bronze entities")
    args = parser.parse_args(argv)

    spark = session(f"bronze-{args.batch}")
    specs = [s for s in load_all().values() if s.layer == "bronze"]
    if args.entity:
        specs = [s for s in specs if s.name == args.entity or s.table == args.entity]

    counts = {}
    for spec in sorted(specs, key=lambda s: s.name):
        counts[spec.table] = load_batch(spark, spec, args.root, args.batch)

    print(json.dumps({"batch": args.batch, "rows": counts}, indent=2))
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
