"""Unit tests for the SCD2 transformation logic, on a local Spark session.

These are the tests review-05 H-01 said were missing and review-06 C-01
proved were needed: a three-row deletion case here would have caught the
resurrection long before an agent reproduced it against the cluster.

They exercise the pure DataFrame functions only: no Delta, no MinIO, no
metastore. The Delta-coupled paths (the MERGE application, convergence across
real batches) are covered by the live convergence check in the plan's
verification.

They skip where pyspark is absent (the host and CI run without it, by
design: the cluster's pyspark comes from the image, and a second local copy
that could disagree with it is the failure ADR 0003 exists to prevent). Run
them with `make test-spark`, which executes inside the driver container.
"""

from __future__ import annotations

import pytest

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402

from lakehouse.scd2 import (  # noqa: E402
    FOREVER,
    rebuild_timeline,
    refuse_empty_snapshot,
    snapshot_deletions,
)
from lakehouse.spec import load_all  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("test-scd2")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(scope="module")
def party_spec():
    return load_all()["silver_party"]


def versions(spark, rows):
    """Rows shaped like silver_party's attributes, minimal columns varied."""
    return spark.createDataFrame(
        [
            {
                "party_id": r[0],
                "full_name": r[3] if len(r) > 3 else "Same Name",
                "address_line": r[1],
                "suburb": "Newtown",
                "state": "NSW",
                "postcode": "2042",
                "risk_rating": "LOW",
                "segment": "RETAIL",
                "updated_at": r[2],
            }
            for r in rows
        ],
        "party_id string, full_name string, address_line string, suburb string, "
        "state string, postcode string, risk_rating string, segment string, "
        "updated_at string",
    ).withColumn("updated_at", pyspark.sql.functions.col("updated_at").cast("timestamp"))


def timeline(spark, party_spec, rows):
    out = rebuild_timeline(versions(spark, rows), party_spec)
    return sorted(
        out.select("effective_from", "effective_to", "is_current", "address_line").collect(),
        key=lambda r: r["effective_from"],
    )


def test_same_day_versions_get_timestamp_grained_ranges(spark, party_spec):
    """Defect 2: two changes in one day are two versions, ranges abutting."""
    rows = [
        ("P1", "1 Old Road", "2026-01-15 09:00:00"),
        ("P1", "2 Same Day Street", "2026-01-15 11:15:00"),
        ("P1", "3 Same Day Terrace", "2026-01-15 16:45:00"),
    ]
    result = timeline(spark, party_spec, rows)

    assert len(result) == 3
    # Half-open, contiguous: each version ends where the next begins.
    assert str(result[0]["effective_to"]) == "2026-01-15 11:15:00"
    assert str(result[1]["effective_to"]) == "2026-01-15 16:45:00"
    assert [r["is_current"] for r in result] == [False, False, True]


def test_first_version_starts_at_the_beginning_of_time(spark, party_spec):
    """ADR 0008: facts predating the first extract must still resolve."""
    result = timeline(spark, party_spec, [("P1", "1 Only Road", "2026-01-15 09:00:00")])

    assert str(result[0]["effective_from"]) == "1900-01-01 00:00:00"
    assert str(result[0]["effective_to"]) == FOREVER
    assert result[0]["is_current"]


def test_out_of_order_arrival_converges_to_the_sorted_timeline(spark, party_spec):
    """Defect 3: arrival order must not matter, only the sequencing column."""
    in_order = [
        ("P1", "1 First Road", "2026-01-01 08:00:00"),
        ("P1", "2 Second Road", "2026-02-01 08:00:00"),
        ("P1", "3 Third Road", "2026-03-01 08:00:00"),
    ]
    shuffled = [in_order[2], in_order[0], in_order[1]]

    assert timeline(spark, party_spec, in_order) == timeline(spark, party_spec, shuffled)


def test_untracked_change_opens_no_version(spark, party_spec):
    """full_name is untracked: a correction must not fork history."""
    rows = [
        ("P1", "1 Same Road", "2026-01-15 09:00:00", "Old Name"),
        ("P1", "1 Same Road", "2026-02-15 09:00:00", "Corrected Name"),
    ]
    result = timeline(spark, party_spec, rows)

    assert len(result) == 1
    assert result[0]["is_current"]


def test_exact_duplicates_collapse(spark, party_spec):
    """Defect 1: a duplicated row is one version, not two."""
    rows = [
        ("P1", "1 Dup Road", "2026-01-15 09:00:00"),
        ("P1", "1 Dup Road", "2026-01-15 09:00:00"),
    ]
    assert len(timeline(spark, party_spec, rows)) == 1


def bronze_like(spark, appearances):
    """(key, batch) pairs shaped like the bronze columns the derivation reads."""
    return spark.createDataFrame(
        [{"party_id": k, "_batch_id": b} for k, b in appearances],
        "party_id string, _batch_id string",
    )


def test_trailing_absence_is_deletion_dated_at_first_missing_batch(spark):
    """The C-01 semantics: in batch 1, gone from 2 and 3 -> deleted at 2."""
    bronze = bronze_like(
        spark,
        [
            ("GONE", "2026-01-15"),
            ("ALIVE", "2026-01-15"),
            ("ALIVE", "2026-02-15"),
            ("ALIVE", "2026-03-15"),
            ("LATE", "2026-02-15"),
            ("LATE", "2026-03-15"),
        ],
    )
    deleted = {
        r["party_id"]: str(r["deleted_ts"])
        for r in snapshot_deletions(bronze, "party_id").collect()
    }

    assert deleted == {"GONE": "2026-02-15 00:00:00"}


def test_reappearance_means_never_deleted(spark):
    """ADR 0010 retracts the gap: absent mid-stream, present later -> alive."""
    bronze = bronze_like(
        spark,
        [("FLICKER", "2026-01-15"), ("FLICKER", "2026-03-15"), ("ALIVE", "2026-03-15")],
    )
    assert snapshot_deletions(bronze, "party_id").count() == 0


def test_derivation_ignores_which_batch_is_being_processed(spark):
    """The C-01 regression, in unit form: the derived set is a function of
    bronze alone, so replaying any batch cannot change it. The old mechanism
    compared against the batch in hand, which is exactly what resurrected the
    deleted parties."""
    import inspect

    from lakehouse import scd2

    signature = inspect.signature(snapshot_deletions)
    assert "batch" not in str(signature), "derivation must not see the current batch"
    assert not hasattr(scd2, "close_vanished"), "the batch-relative mechanism must stay dead"


def test_single_batch_means_no_deletions(spark):
    bronze = bronze_like(spark, [("A", "2026-01-15"), ("B", "2026-01-15")])
    assert snapshot_deletions(bronze, "party_id").count() == 0


def test_empty_snapshot_is_refused(spark, party_spec):
    """Review-06 M-02: an empty extract must fail loudly, not delete the world."""
    empty = versions(spark, []).limit(0)

    with pytest.raises(RuntimeError, match="Refusing to run"):
        refuse_empty_snapshot(empty, party_spec)


def test_empty_snapshot_passes_for_non_snapshot_entities(spark):
    """In an incremental extract a missing row means nothing; the guard is a
    property of the entity, not a blanket rule."""
    account = load_all()["silver_account"]
    empty = bronze_like(spark, []).limit(0)

    refuse_empty_snapshot(empty, account)  # must not raise
