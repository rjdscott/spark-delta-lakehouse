# Phase 06: Gold dimensions

## Goal

Conformed dimensions built on silver, not rebuilt from bronze. `dim_party` with
hash surrogate keys derived from the business key plus `effective_from`, so
keys are stable across environments and reprocessing rather than depending on
insertion order. Then `dim_account`, `dim_date` and `dim_merchant_category`.

Building these from silver rather than from bronze is the thesis in practice.
If a dimension here reaches past silver for entity logic, the argument the repo
makes is false in its own codebase.

## Tasks

- [ ] Hash surrogate key helper: business key plus `effective_from`, applied
      through the spec's surrogate key strategy rather than per dimension.
- [ ] `dim_party` from silver party, preserving the SCD2 effective ranges.
- [ ] `dim_account` from silver account.
- [ ] `dim_date`, generated across the range the facts need, with the columns a
      banking date dimension actually gets asked for.
- [ ] `dim_merchant_category`, including a member for the nulls the generator
      plants. Nulls in a dimension attribute are a modelling decision, not an
      accident to filter.
- [ ] Grain declared in the spec, echoed in the module docstring, written into
      the Delta table comment. All three must agree.
- [ ] Tests parametrised across dimension specs: grain uniqueness, surrogate
      key stability across a full rebuild, no nulls in key columns.
- [ ] ADR: surrogate key strategy. The rejected option is identity columns, and
      the consequence to state is what hashing costs, including collision
      reasoning and what happens if the business key changes shape.

## Verification

```bash
make check
uv run python -m lakehouse.gold --tables dim
uv run pytest tests/test_dimensions.py -q

# stability: rebuild from scratch, keys must not move
uv run python -m lakehouse.gold --tables dim --reset
uv run pytest tests/test_dimensions.py::test_surrogate_keys_are_stable -q
```

## Artifacts

- `src/lakehouse/gold/dim_party.py` and siblings
- `src/lakehouse/gold/keys.py`
- `tests/test_dimensions.py`
- `docs/adr/NNNN-<hash-surrogate-keys>.md`

## Progress log

Dated appends only. Newest at the bottom.
