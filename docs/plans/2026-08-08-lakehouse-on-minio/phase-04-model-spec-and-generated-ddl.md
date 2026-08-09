# Phase 04: Model spec, loader, generated DDL

## Goal

`model/` becomes the modelling layer and the source of truth: grain as a
sentence, business key, history type and sequencing column, attributes with
tracked flags, relationships. A loader validates it and DDL is generated from
it, so physical tables are derived rather than handwritten and the grain
reaches the catalog instead of staying in a YAML file nobody opens.

## Tasks

- [x] Specs for bronze and silver, written before the loader.
- [x] `src/lakehouse/spec.py`: load, validate, fail with the file and field.
- [x] Rejection rules: unknown keys, non-sentence grain, missing sequencing
      column, dangling relationship, SCD2 with no tracked attributes.
- [x] `src/lakehouse/ddl.py`: CREATE TABLE with column comments, the grain as
      the table comment, and the model facts as table properties.
- [x] Tests for every rejection rule plus the DDL contract.
- [x] Gold specs, written in phase 08 once the fields were known.

## Verification

```bash
make check
PYTHONPATH=src uv run python -c "from lakehouse.spec import load_all; print(load_all().keys())"
```

## Artifacts

- `model/*.yml`, `src/lakehouse/spec.py`, `src/lakehouse/ddl.py`
- `tests/test_spec.py`

## Progress log

2026-08-08: Six specs, bronze and silver. Loader validates and DDL generates,
31 tests green in 1.1s.

Gold specs are deliberately not written yet. The guardrail is that the spec
describes only what already varies across existing entities, and gold entities
do not exist, so their fields would be guesses. Writing them now would also
invite schema fields that exactly one spec uses, which is the failure mode the
guardrail exists to prevent. They land in phase 08 alongside the tables.

Two YAML traps, both caught by the validator on first run rather than showing
up later as wrong data:

- `type: decimal(18,2)` inside a flow mapping splits on the comma, so the
  parser saw a key called `2)`. Quoting the type fixes it.
- A bare `on:` key parses as boolean `True` under YAML 1.1. Rather than quote
  it everywhere, the relationship field is named `column`. Choosing a key that
  cannot be misread beats remembering to quote one that can.

Lineage columns and SCD2 validity columns are generated rather than declared,
because they do not vary: every bronze table gets `_ingest_ts`,
`_source_file` and `_batch_id`, and every SCD2 table gets `effective_from`,
`effective_to` and `is_current`. Putting them in the spec would be repeating a
constant in six files.
