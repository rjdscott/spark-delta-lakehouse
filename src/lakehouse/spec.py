"""Load and validate the model specs in `model/`.

The spec is the modelling layer and the source of truth. It declares what a
row means (grain), how a row is identified (business key), how change is
handled (history type and sequencing column), which attributes open a new
version when they change (tracked), and how entities relate.

Four things read it, which is what makes this modelling rather than
documentation:

1. DDL generation, including the grain as the table comment.
2. Test generation: grain uniqueness, SCD2 non-overlap, referential integrity.
3. Diagram generation: the ERD and the bus matrix.
4. Transformation contracts: the SCD2 builder reads `history.type` and
   `sequence_by` here rather than hardcoding them per entity.

**The guardrail.** The schema below describes only what already varies across
the specs that exist. A field appearing in exactly one spec does not belong in
it. There is no inheritance, no macros, no expression language and no plugin
registry, and there should not be: this is a declarative model, not a homegrown
framework, and the difference is discipline about scope. If a change here
starts to look like a language, write the logic directly instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MODEL_DIR = Path(__file__).resolve().parents[2] / "model"

LAYERS = {"bronze", "silver", "gold"}
KINDS = {"entity", "dimension", "fact"}
HISTORY_TYPES = {"append", "scd1", "scd2"}
TYPE_PATTERN = re.compile(r"^(string|date|timestamp|boolean|int|bigint|decimal\(\d+,\d+\))$")

ATTRIBUTE_KEYS = {"name", "type", "tracked", "nullable", "comment"}
# Not "on": YAML 1.1 parses a bare `on` as the boolean True, so the key
# vanishes and the error surfaces somewhere unrelated.
RELATIONSHIP_KEYS = {"to", "column", "kind"}
SPEC_KEYS = {
    "name",
    "layer",
    "kind",
    "grain",
    "source_file",
    "source_spec",
    "business_key",
    "history",
    "attributes",
    "relationships",
    "absence_means_deletion",
    "surrogate_key",
}


class SpecError(ValueError):
    """Raised with the file and the field, because a schema error with neither
    is a scavenger hunt."""


@dataclass(frozen=True)
class Attribute:
    name: str
    type: str
    tracked: bool = False
    nullable: bool = False
    comment: str | None = None


@dataclass(frozen=True)
class Relationship:
    to: str
    column: str
    kind: str


@dataclass(frozen=True)
class Spec:
    name: str
    layer: str
    kind: str
    grain: str
    business_key: tuple[str, ...]
    history_type: str
    sequence_by: str
    attributes: tuple[Attribute, ...]
    # Two fields rather than one overloaded `source`: bronze reads a file,
    # every other layer reads another spec. One name for both meanings needs
    # a layer-dependent validation branch, and invites the next entity to
    # pick the wrong one.
    # 'hash' or absent. The inputs are derivable rather than declared: the
    # business key, plus effective_from when the entity keeps history.
    surrogate_key: str | None = None
    absence_means_deletion: bool = False
    source_file: str | None = None
    source_spec: str | None = None
    relationships: tuple[Relationship, ...] = ()

    @property
    def table(self) -> str:
        """Catalog name: the layer is the database, the entity is the table."""
        return f"{self.layer}.{self.name.removeprefix(self.layer + '_')}"

    def attribute(self, name: str) -> Attribute:
        for a in self.attributes:
            if a.name == name:
                return a
        raise SpecError(f"{self.name}: no attribute named {name}")

    @property
    def tracked(self) -> tuple[Attribute, ...]:
        return tuple(a for a in self.attributes if a.tracked)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecError(message)


def _unknown(where: str, got, allowed: set[str]) -> None:
    extra = set(got) - allowed
    _require(not extra, f"{where}: unknown keys {sorted(extra)}")


def parse(raw: dict, origin: str) -> Spec:
    _unknown(origin, raw, SPEC_KEYS)

    for key in ("name", "layer", "kind", "grain", "business_key", "history", "attributes"):
        _require(key in raw, f"{origin}: missing required key '{key}'")

    _require(raw["layer"] in LAYERS, f"{origin}: layer must be one of {sorted(LAYERS)}")
    _require(raw["kind"] in KINDS, f"{origin}: kind must be one of {sorted(KINDS)}")

    # A grain that is not a sentence is a column list wearing a disguise, and
    # it is the single most common way a model goes wrong unnoticed.
    grain = raw["grain"].strip()
    _require(grain.endswith("."), f"{origin}: grain must be a sentence ending in a full stop")
    _require(len(grain.split()) >= 5, f"{origin}: grain is too terse to be a sentence")

    history = raw["history"]
    _unknown(f"{origin}.history", history, {"type", "sequence_by"})
    _require(
        history.get("type") in HISTORY_TYPES,
        f"{origin}: history.type must be one of {sorted(HISTORY_TYPES)}",
    )
    _require(
        bool(history.get("sequence_by")),
        f"{origin}: history.sequence_by is required, there is no default ordering",
    )

    attributes = []
    for item in raw["attributes"]:
        _unknown(f"{origin}.attributes", item, ATTRIBUTE_KEYS)
        _require("name" in item and "type" in item, f"{origin}: attribute needs name and type")
        _require(
            bool(TYPE_PATTERN.match(item["type"])),
            f"{origin}: attribute '{item['name']}' has unsupported type '{item['type']}'",
        )
        attributes.append(Attribute(**item))

    names = [a.name for a in attributes]
    _require(len(names) == len(set(names)), f"{origin}: duplicate attribute names")

    for key in raw["business_key"]:
        _require(key in names, f"{origin}: business_key '{key}' is not an attribute")
    _require(
        history["sequence_by"] in names,
        f"{origin}: sequence_by '{history['sequence_by']}' is not an attribute",
    )

    if raw.get("surrogate_key"):
        _require(
            raw["surrogate_key"] == "hash",
            f"{origin}: surrogate_key must be 'hash'; identity columns are not stable "
            "across environments or reprocessing",
        )

    if raw.get("absence_means_deletion"):
        _require(
            history["type"] == "scd2",
            f"{origin}: absence_means_deletion needs scd2, there is nothing to close otherwise",
        )

    if history["type"] == "scd2":
        _require(
            any(a.tracked for a in attributes),
            f"{origin}: scd2 with no tracked attributes would never open a version",
        )

    relationships = []
    for item in raw.get("relationships", ()):
        _unknown(f"{origin}.relationships", item, RELATIONSHIP_KEYS)
        _require(
            item["column"] in names,
            f"{origin}: relationship column '{item['column']}' is not an attribute",
        )
        relationships.append(Relationship(**item))

    return Spec(
        name=raw["name"],
        layer=raw["layer"],
        kind=raw["kind"],
        grain=grain,
        surrogate_key=raw.get("surrogate_key"),
        absence_means_deletion=bool(raw.get("absence_means_deletion", False)),
        source_file=raw.get("source_file"),
        source_spec=raw.get("source_spec"),
        business_key=tuple(raw["business_key"]),
        history_type=history["type"],
        sequence_by=history["sequence_by"],
        attributes=tuple(attributes),
        relationships=tuple(relationships),
    )


def load_all(directory: Path | None = None) -> dict[str, Spec]:
    directory = directory or MODEL_DIR
    specs: dict[str, Spec] = {}
    for path in sorted(directory.glob("*.yml")):
        spec = parse(yaml.safe_load(path.read_text()), path.name)
        _require(spec.name == path.stem, f"{path.name}: name '{spec.name}' must match the filename")
        specs[spec.name] = spec

    # Cross-spec checks come last, because they need the whole set. A dangling
    # relationship is the error most likely to survive review.
    for spec in specs.values():
        _require(
            bool(spec.source_file) != bool(spec.source_spec),
            f"{spec.name}: exactly one of source_file and source_spec is required",
        )
        if spec.source_spec:
            _require(
                spec.source_spec in specs,
                f"{spec.name}: source_spec '{spec.source_spec}' is not a spec",
            )
        for rel in spec.relationships:
            _require(rel.to in specs, f"{spec.name}: relationship to '{rel.to}' is not a spec")
    return specs
