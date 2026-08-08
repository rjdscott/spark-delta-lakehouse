"""Generate Delta DDL from the model specs.

Physical tables are derived, never handwritten. That is the point: if the
table and the spec can disagree, the spec is documentation rather than a
model, and documentation drifts.

The grain sentence is written into the table comment, so it is visible from
`DESCRIBE EXTENDED` rather than only in a YAML file nobody opens. A catalog
whose tables carry their grain is a catalog worth browsing.
"""

from __future__ import annotations

from .spec import Spec

# Columns bronze adds to every source row. They are lineage, not business
# data, which is why they are prefixed and why they live here rather than in
# each spec: they do not vary, and the spec describes only what varies.
LINEAGE_COLUMNS = (
    ("_ingest_ts", "timestamp", "When this row was written to bronze"),
    ("_source_file", "string", "The extract file this row was read from"),
    ("_batch_id", "string", "The batch date of the extract"),
)

# Columns an SCD2 table needs to express a version's validity. Also invariant,
# also therefore not in the spec.
SCD2_COLUMNS = (
    ("effective_from", "timestamp", "Inclusive start of this version's validity"),
    ("effective_to", "timestamp", "Exclusive end of this version's validity, null if current"),
    ("is_current", "boolean", "True for exactly one version per business key"),
)


def columns(spec: Spec) -> list[tuple[str, str, str | None]]:
    """Physical columns: the declared attributes plus whatever the layer adds."""
    out = [(a.name, a.type, a.comment) for a in spec.attributes]
    if spec.layer == "bronze":
        out += [(n, t, c) for n, t, c in LINEAGE_COLUMNS]
    if spec.history_type == "scd2":
        out += [(n, t, c) for n, t, c in SCD2_COLUMNS]
    return out


def _escape(text: str) -> str:
    return text.replace("'", "''")


def create_table(spec: Spec, location: str) -> str:
    """A single CREATE TABLE statement, external, at an explicit location.

    External rather than managed: the Delta log in object storage is the
    durable record, and dropping a table should not delete the data. It also
    keeps the catalog swappable, since the tables can be re-registered
    elsewhere from their locations.
    """
    body = ",\n".join(
        f"  {name} {type_}" + (f" COMMENT '{_escape(comment)}'" if comment else "")
        for name, type_, comment in columns(spec)
    )
    properties = ", ".join(
        [
            f"'lakehouse.grain' = '{_escape(spec.grain)}'",
            f"'lakehouse.business_key' = '{','.join(spec.business_key)}'",
            f"'lakehouse.history_type' = '{spec.history_type}'",
            f"'lakehouse.sequence_by' = '{spec.sequence_by}'",
        ]
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {spec.table} (\n{body}\n)\n"
        f"USING DELTA\n"
        f"COMMENT '{_escape(spec.grain)}'\n"
        f"LOCATION '{location}'\n"
        f"TBLPROPERTIES ({properties})"
    )


def create_database(layer: str) -> str:
    return f"CREATE DATABASE IF NOT EXISTS {layer}"
