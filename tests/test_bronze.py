"""Unit tests for bronze's extract reading, on a local Spark session.

Review-07 H-16: the `_rescued_data` branch threw AnalysisException on every
input it existed to survive, and nothing had ever executed it. These tests
run it. Same skip rule as test_scd2: pyspark lives in the image, so run with
`make test-spark`.
"""

from __future__ import annotations

import json

import pytest

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402

from lakehouse.bronze import RESCUED_COLUMN, read_extract  # noqa: E402
from lakehouse.spec import load_all  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("test-bronze")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(scope="module")
def party_spec():
    return load_all()["bronze_party"]


def write_csv(path, header, rows):
    lines = [",".join(header)] + [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def test_unexpected_column_is_rescued_not_fatal(spark, party_spec, tmp_path):
    """Defect 8: a source that adds a column must land it in _rescued_data."""
    declared = [a.name for a in party_spec.attributes]
    header = declared + ["marketing_consent"]
    row = [f"v{i}" for i in range(len(declared))] + ["Y"]
    path = write_csv(tmp_path / "extra.csv", header, [row])

    out = read_extract(spark, party_spec, path, "2026-03-15").collect()

    assert len(out) == 1
    rescued = json.loads(out[0][RESCUED_COLUMN])
    assert rescued == {"marketing_consent": "Y"}
    # The declared columns still arrive, and only they become table columns.
    assert out[0][declared[0]] == "v0"


def test_missing_declared_column_refuses_loudly(spark, party_spec, tmp_path):
    """Review-07 M-17: an explicit schema binds by position, so a short
    header would silently shift every later column. Refuse instead."""
    declared = [a.name for a in party_spec.attributes]
    short = [c for c in declared if c != "segment"]
    row = [f"v{i}" for i in range(len(short))]
    path = write_csv(tmp_path / "short.csv", short, [row])

    with pytest.raises(ValueError, match="segment"):
        read_extract(spark, party_spec, path, "2026-03-15")


def test_clean_extract_rescues_nothing(spark, party_spec, tmp_path):
    declared = [a.name for a in party_spec.attributes]
    row = [f"v{i}" for i in range(len(declared))]
    path = write_csv(tmp_path / "clean.csv", declared, [row])

    out = read_extract(spark, party_spec, path, "2026-03-15").collect()

    assert len(out) == 1
    assert out[0][RESCUED_COLUMN] is None
