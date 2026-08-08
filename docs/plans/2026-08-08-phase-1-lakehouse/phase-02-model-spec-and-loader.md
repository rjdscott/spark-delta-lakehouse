# Phase 02: Model spec and loader

## Goal

The `model/` directory becomes the source of truth: one YAML per entity
declaring layer, kind, grain as a sentence, business key, surrogate key
strategy, history type and sequencing column, attributes with tracked and
untracked flags, and relationships. A loader reads and validates them. Nothing
consumes the spec yet beyond validation, which is the point: the schema gets
fixed before four separate consumers start depending on accidents of it.

The guardrail from the brief is the hard part of this phase, not the parsing.
The spec describes only what already varies across the existing entities. A
field that appears in exactly one spec does not belong in the schema. No
inheritance, no macros, no expression language, no plugin registry. If this
phase starts building a DSL, stop and write the logic directly instead.

## Tasks

- [ ] Write the specs for every entity the plan will build, all layers, before
      writing the loader. Writing them first is what reveals which fields
      genuinely vary.
- [ ] `src/lakehouse/spec.py`: load, parse, and validate. Validation failures
      name the file and the field.
- [ ] Reject what must be rejected: unknown keys, a missing grain sentence, a
      history type without a sequencing column, a relationship pointing at an
      entity that does not exist.
- [ ] Tests: one valid spec loads; each rejection rule has a failing case.
- [ ] ADR: spec-driven modelling and its scope limits. The rejected option to
      record is the obvious one, a generalised framework, and the consequence
      to state is what this design cannot express.

## Verification

```bash
make check
uv run python -c "from lakehouse.spec import load_all; print(sorted(s.name for s in load_all()))"
uv run pytest tests/test_spec.py -q
```

Then read the specs back as a stranger would: does every grain sentence
actually describe one row?

## Artifacts

- `model/*.yml`, one per entity
- `src/lakehouse/spec.py`
- `tests/test_spec.py`
- `docs/adr/NNNN-<spec-driven-modelling>.md`

## Progress log

Dated appends only. Newest at the bottom.
