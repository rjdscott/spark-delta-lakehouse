# Phase 05: Silver SCD2 party

## Goal

Party as SCD Type 2 via a handwritten MERGE, including the union pattern that
MERGE forces: one action is permitted per source row, and closing an old
version while inserting a new one is two actions, so the source must be
unioned with itself. The builder reads `history.type` and `sequence_by` from
the spec rather than hardcoding them, so adding an entity later means adding a
spec, not copying this module.

This phase is alone in its PR because it is the hardest correctness problem in
the repo, and because the seeded defects aim three separate attacks at it: a
party whose address changes twice within one day, records arriving out of
sequence, and parties that vanish between batches.

## Tasks

- [ ] SCD2 builder driven by `history.type` and `sequence_by` from the spec.
- [ ] The union pattern, with a comment explaining why it exists. A reader who
      has never hit the one-action-per-source-row limit should learn it here.
- [ ] Intra-day versioning: two changes on the same day produce two versions,
      which means the effective range cannot be date-grained.
- [ ] Out-of-order arrivals: an `updated_at` earlier than a version already
      loaded must not corrupt the timeline.
- [ ] Tracked versus untracked attributes from the spec: a change to an
      untracked attribute must not open a new version.
- [ ] Tests, all parametrised across specs rather than written per table:
      no overlapping effective ranges per business key; exactly one current row
      per key; no gaps in the timeline.
- [ ] Out-of-order resilience test: replaying batches in the wrong order
      converges to the same final state as replaying them in order.
- [ ] ADR: SCD type per entity. Party is type 2, account is type 1, and the
      reason is about how each is queried, not about which is more advanced.

## Verification

```bash
make check
uv run python -m lakehouse.silver --entity party --batch 1
uv run python -m lakehouse.silver --entity party --batch 2
uv run python -m lakehouse.silver --entity party --batch 3
uv run pytest tests/test_scd2.py -q

# replay out of order, then compare
uv run python -m lakehouse.silver --entity party --batch 3 --reset
uv run python -m lakehouse.silver --entity party --batch 1
uv run python -m lakehouse.silver --entity party --batch 2
uv run pytest tests/test_scd2.py::test_convergence -q
```

Inspect the party that changes twice in one day by hand before calling this
done. The row count is not the interesting part; the effective range boundaries
are.

## Artifacts

- `src/lakehouse/silver/party.py`
- `src/lakehouse/silver/scd2.py`, the spec-driven builder
- `tests/test_scd2.py`
- `docs/adr/NNNN-<scd-type-per-entity>.md`

## Progress log

Dated appends only. Newest at the bottom.
