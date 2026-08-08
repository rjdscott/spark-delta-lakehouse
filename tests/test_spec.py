"""The spec's contract: it loads, and it refuses what it should refuse.

Every rejection rule gets a case. A validator that only has happy-path tests
is a validator nobody knows the limits of.
"""

from __future__ import annotations

import copy

import pytest

from lakehouse import ddl
from lakehouse.spec import SpecError, load_all, parse

VALID = {
    "name": "silver_thing",
    "layer": "silver",
    "kind": "entity",
    "grain": "One row per thing per version of its tracked attributes.",
    "source": "bronze_thing",
    "business_key": ["thing_id"],
    "history": {"type": "scd2", "sequence_by": "updated_at"},
    "attributes": [
        {"name": "thing_id", "type": "string"},
        {"name": "colour", "type": "string", "tracked": True},
        {"name": "updated_at", "type": "timestamp"},
    ],
}


def variant(**changes) -> dict:
    raw = copy.deepcopy(VALID)
    raw.update(changes)
    return raw


def test_the_repos_specs_all_load():
    specs = load_all()

    assert specs["silver_party"].history_type == "scd2"
    assert specs["silver_account"].history_type == "scd1"
    # The defect that makes SCD2 worth having lands on tracked attributes.
    assert "address_line" in {a.name for a in specs["silver_party"].tracked}
    # An untracked change must not open a version.
    assert "full_name" not in {a.name for a in specs["silver_party"].tracked}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (variant(layer="platinum"), "layer must be one of"),
        (variant(kind="table"), "kind must be one of"),
        (variant(grain="One row per thing"), "must be a sentence"),
        (variant(grain="Per thing."), "too terse"),
        (variant(business_key=["nope"]), "is not an attribute"),
        (variant(history={"type": "scd7", "sequence_by": "updated_at"}), "history.type must be"),
        (variant(history={"type": "scd2"}), "sequence_by is required"),
        (variant(history={"type": "scd2", "sequence_by": "nope"}), "is not an attribute"),
        (variant(surprise="value"), "unknown keys"),
    ],
)
def test_invalid_specs_are_rejected_by_field(raw, expected):
    with pytest.raises(SpecError, match=expected):
        parse(raw, "test.yml")


def test_scd2_without_tracked_attributes_is_rejected():
    raw = variant(
        attributes=[
            {"name": "thing_id", "type": "string"},
            {"name": "updated_at", "type": "timestamp"},
        ]
    )
    with pytest.raises(SpecError, match="would never open a version"):
        parse(raw, "test.yml")


def test_unsupported_column_type_is_rejected():
    raw = variant(
        attributes=[
            {"name": "thing_id", "type": "blob"},
            {"name": "colour", "type": "string", "tracked": True},
            {"name": "updated_at", "type": "timestamp"},
        ]
    )
    with pytest.raises(SpecError, match="unsupported type"):
        parse(raw, "test.yml")


def test_ddl_carries_the_grain_into_the_table_comment():
    spec = load_all()["silver_party"]

    statement = ddl.create_table(spec, "s3a://lakehouse/silver/party")

    assert spec.grain in statement
    assert "COMMENT" in statement
    assert "lakehouse.history_type' = 'scd2'" in statement
    assert "LOCATION 's3a://lakehouse/silver/party'" in statement


def test_scd2_tables_get_validity_columns_and_bronze_gets_lineage():
    specs = load_all()

    silver = {name for name, _, _ in ddl.columns(specs["silver_party"])}
    bronze = {name for name, _, _ in ddl.columns(specs["bronze_party"])}

    assert {"effective_from", "effective_to", "is_current"} <= silver
    assert {"_ingest_ts", "_source_file", "_batch_id"} <= bronze
    # Lineage belongs to bronze only; silver is conformed, not raw.
    assert "_source_file" not in silver
