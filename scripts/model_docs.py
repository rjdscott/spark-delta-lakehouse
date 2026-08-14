#!/usr/bin/env python3
"""Generate the model documentation from the specs in `model/`.

Two artifacts, the same rule as the index tables: a diagram maintained by
hand disagrees with the code within a month, so these are derived and
`make docs-check` fails when they are stale.

- The star-schema ERD, spliced between markers in `docs/data-model.md`.
- `docs/BUS_MATRIX.md`, business processes against conformed dimensions,
  written whole.

Both read only `model/*.yml` through the spec loader, so they are exactly as
truthful as the specs, which `conformance()` holds to the physical tables.

    make docs        # rewrite
    make docs-check  # fail if stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lakehouse.spec import Spec, load_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_MODEL = ROOT / "docs" / "data-model.md"
BUS_MATRIX = ROOT / "docs" / "BUS_MATRIX.md"

ERD_START = "<!-- erd:start -->"
ERD_END = "<!-- erd:end -->"


def short(name: str) -> str:
    """gold_dim_party -> dim_party, for diagram labels."""
    return name.removeprefix("gold_")


def erd(specs: dict[str, Spec]) -> str:
    """Mermaid ERD of the gold star: facts, dimensions, and the joins the
    specs declare. Attribute lists stay out; grain sentences say more than
    column inventories and the catalog already carries both."""
    gold = {n: s for n, s in specs.items() if s.layer == "gold"}
    lines = ["```mermaid", "erDiagram"]
    for name, spec in sorted(gold.items()):
        for rel in spec.relationships:
            # many_to_one: many fact rows point at one dimension row.
            lines.append(f'    {short(name)} }}o--|| {short(rel.to)} : "{rel.column}"')
    for name, spec in sorted(gold.items()):
        grain = spec.grain.rstrip(".").replace('"', "'")
        lines.append(f"    {short(name)} {{")
        # Mermaid attributes are `type name "comment"`. Without the type the
        # parser reads the quoted sentence as the name and the block fails.
        lines.append(f'        string grain "{grain}"')
        lines.append("    }")
    lines.append("```")
    return "\n".join(lines)


def bus_matrix(specs: dict[str, Spec]) -> str:
    facts = sorted(
        (s for s in specs.values() if s.layer == "gold" and s.kind == "fact"),
        key=lambda s: s.name,
    )
    dims = sorted(
        (s for s in specs.values() if s.layer == "gold" and s.kind == "dimension"),
        key=lambda s: s.name,
    )

    header = "| Business process | " + " | ".join(short(d.name) for d in dims) + " |"
    rule = "|---" * (len(dims) + 1) + "|"
    rows = []
    for fact in facts:
        joined = {rel.to for rel in fact.relationships}
        cells = " | ".join("X" if d.name in joined else "" for d in dims)
        rows.append(f"| {short(fact.name)} | {cells} |")

    grains = "\n".join(f"- **{short(s.name)}**: {s.grain}" for s in facts + dims)

    return f"""# Bus matrix

Generated from `model/*.yml` by `make docs`. Don't hand-edit: the specs are
the source of truth, and `make docs-check` fails when this file is stale.

Rows are business processes, one per fact table. Columns are the conformed
dimensions. An X means the fact's spec declares the relationship, which is the
same declaration the DDL, the tests and the ERD are generated from.

{header}
{rule}
{chr(10).join(rows)}

A dimension with X in more than one row is conformed: built once in silver,
reused by every process that needs it. That reuse is the argument this repo
exists to make; a second `dim_party` appearing here would mean the argument
had failed in its own codebase.

## Grains

{grains}
"""


def splice(text: str, block: str) -> str:
    if ERD_START not in text or ERD_END not in text:
        raise SystemExit(f"{DATA_MODEL.name}: missing {ERD_START} / {ERD_END} markers")
    pattern = re.escape(ERD_START) + r".*?" + re.escape(ERD_END)
    return re.sub(pattern, lambda _: f"{ERD_START}\n{block}\n{ERD_END}", text, flags=re.S)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing")
    args = parser.parse_args(argv)

    specs = load_all()
    stale = []

    new_page = splice(DATA_MODEL.read_text(), erd(specs))
    if new_page != DATA_MODEL.read_text():
        if args.check:
            stale.append("docs/data-model.md (ERD)")
        else:
            DATA_MODEL.write_text(new_page)
            print("updated docs/data-model.md ERD")

    new_matrix = bus_matrix(specs)
    if not BUS_MATRIX.exists() or BUS_MATRIX.read_text() != new_matrix:
        if args.check:
            stale.append("docs/BUS_MATRIX.md")
        else:
            BUS_MATRIX.write_text(new_matrix)
            print("updated docs/BUS_MATRIX.md")

    if stale:
        print(
            "error: model docs out of date: " + ", ".join(stale) + ". Run `make docs`.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
