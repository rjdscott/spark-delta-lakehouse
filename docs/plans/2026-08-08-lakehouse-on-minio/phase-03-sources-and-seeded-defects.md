# Phase 03: Sources and seeded defects

## Goal

Three retail banking sources as CSV on disk, generated deterministically from
a seed, carrying the seven defects from the brief. The defects are the point:
each one forces a specific behaviour in a later phase, and each is documented
with the behaviour it exercises.

## Tasks

- [x] Deterministic generator, one seeded RNG, sorted iteration everywhere.
- [x] Party and account as full snapshots, transactions as an incremental
      event stream, because a hard delete is only detectable as an absence.
- [x] Plant all seven defects.
- [x] `data/DEFECTS.md`: one entry per defect, the behaviour it exercises, and
      the test that proves it is still there.
- [x] A test per defect, plus byte-identical reproducibility from the seed.
- [x] `make generate` target.

## Verification

```bash
make generate
uv run pytest tests/test_generate.py -q
```

Expected: 9 rows of counts, 8 tests passing in about a second.

## Artifacts

- `src/lakehouse/generate.py`
- `data/DEFECTS.md`
- `tests/test_generate.py`

## Progress log

2026-08-08: Completed. Generator produces about 2,000 parties, 3,000 accounts
and 17,000 transactions per batch across three batch dates, byte-identical
across runs. All seven defects assert as present in 1.0s.

One design decision worth recording: party and account extract as full
snapshots while transactions are incremental. Defect 7 forced it. A hard
delete carries no signal in a delta extract, since an absent row is
indistinguishable from an unchanged one, so detecting deletions at all
requires the extract to be a snapshot. This mirrors how banks actually publish
reference data versus event data.

Defect 1 has a trap worth flagging for phase 06: the duplicates are exact, so
`DISTINCT` looks like the fix, but it would also collapse the two legitimate
same-day versions from defect 2. Deduplication has to be on the business key
plus the sequencing column, not on the whole row.
