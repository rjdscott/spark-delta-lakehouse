"""SCD Type 2: one row per business key per version of its tracked attributes.

This is the hardest correctness problem in the repo, and four of the eight
seeded defects aim at it directly: duplicates, the same-day double change,
out-of-sequence arrival, and hard deletion, whose derived handling
(ADR 0010) is the second half of this module.

**Why the timeline is recomputed rather than appended to.** The obvious
incremental design closes the current row and inserts a new one. It needs the
union pattern, because MERGE permits one action per source row and closing plus
inserting is two, so the source is unioned with itself. That design is correct
only while records arrive in order. Defect 3 plants a record whose `updated_at`
predates a version already loaded, and inserting it means rewriting the
`effective_to` of the row before it and the `effective_from` of the row after.
MERGE cannot do that in one pass, and skipping such records fails the property
that matters more: replaying batches in any order must converge to the same
final state.

So for every business key the batch touches, the whole timeline is rebuilt
from bronze, which holds every version ever landed. Not from the stored
table: the stored table holds only rebuild survivors, and a version pruned
as a no-op stops being a no-op the moment a later batch delivers an
out-of-order change before it. Sourcing the rebuild from the stored table
made convergence order-lucky (review-07 H-09); sourcing it from bronze makes
it order-independent by construction, because every build of a key is a pure
function of the full history. ADR 0011 records the decision, the same
argument ADR 0010 made for deletions: anything written-once loses to a
rebuild.

**Untracked attributes are frozen at the version that opened them.** A
version records the row that opened it; a later row that changes only
untracked attributes is a no-op and leaves no trace. `tracked: false` means
"changes to this do not matter to history", not "type 1 overwrite". Pinned
by test, so the choice is deliberate rather than emergent.

**Effective ranges are timestamp-grained, not date-grained.** Defect 2 changes
one party's address twice in a single day. A `DATE` effective_from would
collapse those two versions into one, or produce a zero-length range, and the
party would silently lose a version.

**Only tracked attributes open a version.** Party arrives as a full snapshot,
so every party appears in every batch. Without this, every batch would open a
version for every party and the table would grow by two thousand rows a month
while saying nothing.
"""

from __future__ import annotations

import argparse
import json

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from .catalog import conformance, ensure_table, session
from .silver import coerce
from .spec import Spec, load_all

# The open end of a current version. A null would be more honest but makes
# every as-of join in gold carry a null check, and a far-future sentinel makes
# the range predicate a plain BETWEEN.
FOREVER = "9999-12-31 23:59:59"

# The earliest version of a key starts at the beginning of time, not when the
# source first told us about it. We know when we first *saw* an attribute, not
# when it *became* true, and a dimension whose first version starts at first
# sighting cannot resolve any fact that predates the first extract, which is
# most facts in a first load. See ADR 0008.
BEGINNING = "1900-01-01 00:00:00"


def _versions(df: DataFrame, spec: Spec) -> DataFrame:
    """Attribute columns plus the sequencing column, nothing else."""
    return df.select(*[a.name for a in spec.attributes])


def rebuild_timeline(history: DataFrame, spec: Spec) -> DataFrame:
    """Turn a pile of versions for many keys into effective-dated rows.

    `history` is every version known for the affected keys, in any order, with
    duplicates. What comes back is one row per genuine change, with contiguous
    ranges and exactly one current row per key.
    """
    keys = [F.col(k) for k in spec.business_key]
    tracked = [a.name for a in spec.tracked]

    # Exact duplicates carry no information. Two rows with the same key and
    # the same sequencing value but different tracked attributes are a source
    # contradiction; ordering by the tracked columns makes the winner
    # deterministic rather than whichever the shuffle produced.
    ordered = Window.partitionBy(*keys, F.col(spec.sequence_by)).orderBy(
        *[F.col(c).asc_nulls_last() for c in tracked]
    )
    deduped = (
        history.dropDuplicates()
        .withColumn("_r", F.row_number().over(ordered))
        .filter(F.col("_r") == 1)
        .drop("_r")
    )

    # A version only exists where a tracked attribute actually changed. The
    # first version for a key always counts.
    timeline = Window.partitionBy(*keys).orderBy(F.col(spec.sequence_by).asc())
    # A separator, and a marker distinct from the empty string. Without the
    # separator ("ab", "c") and ("a", "bc") fingerprint identically and a real
    # change goes undetected; without the marker a null and an empty string
    # are the same version. Written as escapes: literal control bytes in the
    # source make the file unimportable with "source code string cannot
    # contain null bytes", and neither ruff nor grep -P reliably flags it.
    fingerprint = F.concat_ws(
        "\u001f",
        *[F.coalesce(F.col(c).cast("string"), F.lit("\u0000")) for c in tracked],
    )
    changed = (
        deduped.withColumn("_fingerprint", fingerprint)
        .withColumn("_previous", F.lag("_fingerprint").over(timeline))
        .filter(F.col("_previous").isNull() | (F.col("_fingerprint") != F.col("_previous")))
        .drop("_fingerprint", "_previous")
    )

    # Ranges are half open: [effective_from, effective_to). A transaction at
    # exactly the instant of a change belongs to the new version.
    first = F.row_number().over(timeline) == 1
    return (
        changed.withColumn(
            "effective_from",
            F.when(first, F.lit(BEGINNING).cast("timestamp")).otherwise(F.col(spec.sequence_by)),
        )
        .withColumn(
            "effective_to",
            F.coalesce(
                F.lead(F.col(spec.sequence_by)).over(timeline),
                F.lit(FOREVER).cast("timestamp"),
            ),
        )
        .withColumn(
            "is_current",
            F.lead(F.col(spec.sequence_by)).over(timeline).isNull(),
        )
    )


def snapshot_deletions(bronze: DataFrame, key: str) -> DataFrame:
    """The deleted keys, derived from every landed snapshot batch.

    Deletion is a trailing absence: a key missing from the latest landed
    snapshot is deleted, dated at the first batch it failed to appear in. A
    key absent mid-stream but present later was never deleted. See ADR 0010.

    Derived, not stored, and that is the entire fix for review-06 C-01: the
    old mechanism wrote the closure once and compared against a single batch,
    so a timeline rebuild erased it and replaying batch 1 resurrected every
    deleted party. This derivation reads only bronze, which holds every batch,
    so it does not depend on which batch is being processed and re-applying it
    after any rebuild converges in any replay order.

    Returns (key, deleted_ts). Empty for a bronze with a single batch.
    """
    batches = sorted(r[0] for r in bronze.select("_batch_id").distinct().collect())
    if len(batches) < 2:
        return bronze.sparkSession.createDataFrame([], f"{key} string, deleted_ts timestamp")

    latest = batches[-1]
    # Each batch's successor, as a literal mapping. Three batches today; a
    # join against a successor table would be the shape at scale.
    successor = dict(zip(batches, batches[1:], strict=False))
    successor_expr = F.col("last_seen")
    for seen, next_batch in successor.items():
        successor_expr = F.when(F.col("last_seen") == seen, F.lit(next_batch)).otherwise(
            successor_expr
        )

    return (
        bronze.groupBy(key)
        .agg(F.max("_batch_id").alias("last_seen"))
        .filter(F.col("last_seen") != latest)
        .withColumn("deleted_ts", F.to_timestamp(successor_expr))
        .select(key, "deleted_ts")
    )


def refuse_empty_snapshot(incoming: DataFrame, spec: Spec) -> None:
    """An empty extract is a source failure, not a mass deletion.

    Without this, review-06 M-02: a missing party file closed all 1,975
    current parties with exit code 0 and every integrity check green. ADR
    0007 named this guard; ADR 0010 makes it mandatory.
    """
    if spec.absence_means_deletion and incoming.limit(1).count() == 0:
        raise RuntimeError(
            f"{spec.table}: incoming snapshot is empty. Refusing to run, because "
            "processing it would eventually read as the deletion of every key. "
            "If the source genuinely has zero rows, that is a decision for a "
            "human, not a batch job."
        )


# The derived deleted set may not exceed this fraction of current keys. An
# extract that vanishes most of the dimension is a truncated file, not a mass
# offboarding; the zero-row guard alone let a one-row extract close everything
# (review-07 M-10). One entity uses deletion today, so this is a constant, not
# a spec field, per the spec's own discipline.
MAX_DELETION_RATE = 0.10


def deletion_closures(current: DataFrame, deleted: DataFrame, key: str) -> tuple[int, int]:
    """Split the derived deletions into what the merge will apply and what it
    will refuse.

    Counted under the merge's own predicate, so the reported number is what
    actually happens: the old count ignored the inverted-range guard and
    overstated exactly when the guard fired (review-07 M-11). The refused rows
    are stored versions newer than the deletion evidence (review-06 M-12),
    left visibly current on purpose.
    """
    candidates = current.join(deleted, on=key, how="inner")
    applied = candidates.filter(F.col("effective_from") < F.col("deleted_ts")).count()
    refused = candidates.count() - applied
    return applied, refused


def apply_deletions(spark: SparkSession, spec: Spec, source: Spec) -> tuple[int, int]:
    """Re-derive the deleted set and close whatever the rebuild left open.

    Runs after every rebuild, unconditionally, which is what makes closures
    idempotent: a key already closed matches nothing (the condition requires
    is_current), a key resurrected by a replayed batch is re-closed here.

    Returns (closures applied, closures refused by the inverted-range guard).
    """
    if not spec.absence_means_deletion:
        return 0, 0

    key = spec.business_key[0]
    deleted = snapshot_deletions(spark.table(source.table), key)

    current = spark.table(spec.table).filter(F.col("is_current"))
    current_count = current.count()
    deleted_count = deleted.count()
    if current_count and deleted_count / current_count > MAX_DELETION_RATE:
        raise RuntimeError(
            f"{spec.table}: the snapshot stream implies {deleted_count} of "
            f"{current_count} current keys are deleted, above the "
            f"{MAX_DELETION_RATE:.0%} guard. That is a truncated or broken "
            "extract until a human says otherwise."
        )

    count, refused = deletion_closures(current, deleted, key)
    if count:
        (
            DeltaTable.forName(spark, spec.table)
            .alias("t")
            .merge(deleted.alias("s"), f"t.{key} = s.{key}")
            .whenMatchedUpdate(
                # The second clause refuses inverted ranges (review-06 M-12):
                # a corrective re-extract can leave a stored version newer
                # than the deletion evidence, and closing it would produce
                # effective_to < effective_from. The contradiction then stays
                # visible as an is_current key absent from the latest
                # snapshot, which is the honest representation of a source
                # that contradicted itself.
                condition="t.is_current AND t.effective_from < s.deleted_ts",
                set={
                    "effective_to": F.col("s.deleted_ts"),
                    "is_current": F.lit(False),
                },
            )
            .execute()
        )
    return count, refused


def build(spark: SparkSession, spec: Spec, batch_id: str) -> dict:
    ensure_table(spark, spec)
    problems = conformance(spark, spec)
    if problems:
        raise RuntimeError(
            f"{spec.table} does not match its spec, refusing to build:\n  " + "\n  ".join(problems)
        )

    source = load_all()[spec.source_spec]
    incoming = _versions(
        coerce(spark.table(source.table).filter(F.col("_batch_id") == batch_id), spec), spec
    )
    refuse_empty_snapshot(incoming, spec)

    key = spec.business_key[0]
    affected = incoming.select(key).distinct()

    # The full history for the affected keys, from bronze, not from the
    # stored table. Bronze holds every version ever landed, including the
    # no-ops a previous rebuild pruned; the stored table does not, and
    # rebuilding from it made the result depend on replay order
    # (review-07 H-09, ADR 0011). The incoming batch is already in bronze
    # by the time this runs, so history includes it.
    history = _versions(
        coerce(spark.table(source.table).join(affected, on=key, how="semi"), spec), spec
    )

    rebuilt = rebuild_timeline(history, spec)

    # Replace exactly the affected keys. Matching on key plus effective_from
    # lets an unchanged version stay put, an amended one update in place, and a
    # version that no longer exists be deleted, which is what makes a replay of
    # an old batch converge rather than accumulate.
    target = DeltaTable.forName(spark, spec.table)
    (
        target.alias("t")
        .merge(
            rebuilt.alias("s"),
            f"t.{key} = s.{key} AND t.effective_from = s.effective_from",
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .whenNotMatchedBySourceDelete(
            condition=F.col(f"t.{key}").isin([r[key] for r in affected.collect()])
        )
        .execute()
    )

    closed, refused = apply_deletions(spark, spec, source)
    return {
        "rows": spark.table(spec.table).count(),
        "current": spark.table(spec.table).filter(F.col("is_current")).count(),
        "closed_as_deleted": closed,
        "deletions_refused": refused,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    args = parser.parse_args(argv)

    spark = session(f"scd2-{args.batch}")
    specs = [s for s in load_all().values() if s.layer == "silver" and s.history_type == "scd2"]
    result = {
        spec.table: build(spark, spec, args.batch) for spec in sorted(specs, key=lambda s: s.name)
    }
    print(json.dumps({"batch": args.batch, **result}, indent=2))
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
