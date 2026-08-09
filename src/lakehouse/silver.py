"""Silver: one conformed, typed, deduplicated row per business key.

Silver is the shared entity layer. Gold builds on it, and so does anything
else that needs to know what a party or an account currently is. The whole
argument of this repo is that this layer exists once and is reused, rather
than every consumer rebuilding entity logic from bronze.

Three things happen here and nothing else:

1. **Type coercion.** Bronze holds strings because that is what the source
   sent. Silver decides what those strings mean.
2. **Deduplication on the business key.** Not `DISTINCT`. The extracts contain
   exact duplicate rows, and `DISTINCT` would remove them, but it would also
   collapse two legitimate versions of a party that differ only in
   `updated_at`, which is the same-day change the SCD2 builder depends on.
   Deduplication is on the business key plus the sequencing column.
3. **Conformed naming.** Driven by the spec rather than repeated per entity.

No dimensional resolution. Transactions keep their `account_id` and get no
surrogate keys, because resolving a transaction to the dimension version
current at its event time is gold's job, and doing it here is the mistake the
repo argues against.

SCD2 lives in `scd2.py`, because party's history is a harder problem than
this and does not belong in the same module.
"""

from __future__ import annotations

import argparse
import json

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from .catalog import conformance, ensure_table, session
from .spec import Spec, load_all


def coerce(df: DataFrame, spec: Spec) -> DataFrame:
    """Cast bronze's strings to the types the spec declares.

    A value that will not cast becomes null. That is a deliberate choice and
    not a silent one: bronze still holds the original text, so the evidence
    survives, and a null here is recoverable rather than lost.
    """
    return df.select(
        *[
            F.col(attribute.name).cast(attribute.type).alias(attribute.name)
            for attribute in spec.attributes
        ]
    )


def deduplicate(df: DataFrame, spec: Spec) -> DataFrame:
    """One row per business key: the latest by the sequencing column.

    The tiebreak matters. Two rows can share a business key and a sequencing
    value, because the extracts contain exact duplicates, and without a
    deterministic tiebreak the winner varies between runs and idempotency
    tests fail intermittently. Ordering by every column is heavy-handed and
    correct: identical rows tie, and a tie between identical rows has no
    wrong answer.
    """
    ordering = [F.col(spec.sequence_by).desc()] + [
        F.col(a.name).asc_nulls_last() for a in spec.attributes
    ]
    window = Window.partitionBy(*[F.col(k) for k in spec.business_key]).orderBy(*ordering)
    return (
        df.withColumn("_row", F.row_number().over(window)).filter(F.col("_row") == 1).drop("_row")
    )


def upsert_scd1(spark: SparkSession, df: DataFrame, spec: Spec) -> None:
    """Overwrite in place, but only with a newer version.

    The sequencing guard is what makes batches replayable in any order. Defect
    3 plants a record whose `updated_at` predates a version already loaded; a
    plain MERGE without this condition would let it overwrite newer state and
    the layer would depend on arrival order.
    """
    target = DeltaTable.forName(spark, spec.table)
    on = " AND ".join(f"t.{k} = s.{k}" for k in spec.business_key)

    (
        target.alias("t")
        .merge(df.alias("s"), on)
        .whenMatchedUpdateAll(condition=f"s.{spec.sequence_by} > t.{spec.sequence_by}")
        .whenNotMatchedInsertAll()
        .execute()
    )


def build(spark: SparkSession, spec: Spec, batch_id: str) -> int:
    """Advance one silver entity by one batch.

    Batch at a time, not a full rebuild from all of bronze. That is how a real
    pipeline runs, and here it is also the only way the seeded defects mean
    anything: rebuilding from every batch at once makes a late-arriving account
    present from the start, so the orphan references defect 4 plants never
    exist and gold would never create an inferred member. Processing
    incrementally is what makes the timeline real.
    """
    ensure_table(spark, spec)
    problems = conformance(spark, spec)
    if problems:
        raise RuntimeError(
            f"{spec.table} does not match its spec, refusing to build:\n  " + "\n  ".join(problems)
        )

    source = load_all()[spec.source_spec]
    bronze = spark.table(source.table).filter(F.col("_batch_id") == batch_id)

    conformed = deduplicate(coerce(bronze, spec), spec)
    upsert_scd1(spark, conformed, spec)
    return spark.table(spec.table).count()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="batch date, e.g. 2026-01-15")
    parser.add_argument("--entity", help="one entity, default every scd1 silver entity")
    args = parser.parse_args(argv)

    spark = session(f"silver-{args.batch}")
    specs = [s for s in load_all().values() if s.layer == "silver" and s.history_type == "scd1"]
    if args.entity:
        specs = [s for s in specs if s.name == args.entity or s.table == args.entity]

    counts = {
        spec.table: build(spark, spec, args.batch) for spec in sorted(specs, key=lambda s: s.name)
    }
    print(json.dumps({"batch": args.batch, "rows": counts}, indent=2))
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
