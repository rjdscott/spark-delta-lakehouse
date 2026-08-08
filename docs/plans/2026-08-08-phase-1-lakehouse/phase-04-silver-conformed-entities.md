# Phase 04: Silver conformed entities

## Goal

Silver as a genuinely shared entity layer, for everything except party history.
Deduplication on business key, type coercion, conformed naming. Account as SCD
Type 1. Transaction cleansed only, with no dimensional resolution, because
resolving transactions to dimension versions is gold's job and doing it here is
the mistake the whole repo argues against.

Party is deliberately absent from this phase. It lands in 05.

## Tasks

- [ ] Deduplication on business key, handling the exact-duplicate rows planted
      in every source.
- [ ] Type coercion and conformed naming, driven by the spec rather than
      repeated per entity.
- [ ] Account as SCD Type 1, overwriting in place.
- [ ] Transaction cleansed: types, nulls, no joins to dimensions, no surrogate
      keys.
- [ ] Handle the parties hard deleted between batches. Decide and record what
      silver does about a business key that stops arriving; this is a fork, so
      if the answer is not obvious from the brief, write the ADR before coding
      around a guess.
- [ ] Idempotency test for each silver table.
- [ ] Referential sanity: transactions referencing accounts absent from silver
      are counted, not dropped, and the count is asserted rather than assumed.

## Verification

```bash
make check
uv run python -m lakehouse.silver --batch 1
uv run python -m lakehouse.silver --batch 1     # idempotent
uv run pytest tests/test_silver.py -q
```

Then load batches 1, 2, 3 in order and confirm account rows reflect the latest
`updated_at` per business key, not the last row written.

## Artifacts

- `src/lakehouse/silver/account.py`, `src/lakehouse/silver/transaction.py`
- shared dedupe and coercion helpers, spec-driven
- `tests/test_silver.py`

## Progress log

Dated appends only. Newest at the bottom.
