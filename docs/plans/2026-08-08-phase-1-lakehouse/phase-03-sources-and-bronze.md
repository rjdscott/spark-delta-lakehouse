# Phase 03: Sources, seeded defects, bronze

## Goal

Three CSV sources across three sequential batch dates, generated synthetically
and deterministically from a seed, carrying the seven defects the brief
requires. Then bronze: append-only, source-shaped, with `_ingest_ts`,
`_source_file` and `_batch_id`, no dedupe, no renaming, no business logic, and
rescued-data handling for unexpected columns. Physical tables are created from
the spec, never handwritten, which makes this the phase where DDL generation
earns its place rather than being asserted.

The defects are not decoration. Each one exercises a specific behaviour later
phases must handle, and each gets documented in `data/DEFECTS.md` alongside the
behaviour it exercises.

## Tasks

- [ ] Deterministic generator, seeded, producing party (~2000), account (~3000)
      and transaction (~50000) rows across three batch dates.
- [ ] Plant all seven defects: exact duplicate rows in every source; a party
      whose address changes twice in one day; records arriving with
      `updated_at` earlier than a version already loaded; batch 1 transactions
      referencing accounts that first appear in batch 2; `posted_ts` up to five
      days after `txn_ts`; nulls in `risk_rating` and `merchant_category`;
      parties present in batch 1 and absent in batch 2.
- [ ] `data/DEFECTS.md`: one entry per defect, naming the behaviour it
      exercises and the test that will prove it.
- [ ] DDL generation from the spec: Delta table creation, column comments,
      table properties, grain written into the table comment.
- [ ] Bronze ingestion, append-only, with the three lineage columns and
      rescued-data handling.
- [ ] Idempotency test: re-running bronze produces identical row counts and
      content hashes.
- [ ] Regeneration test: the same seed produces byte-identical sources.
- [ ] ADR: integrity enforcement without engine-level constraints. Delta has no
      primary keys; record what replaces them and what that costs.

## Verification

```bash
make check
uv run python -m lakehouse.generate --seed 42
uv run python -m lakehouse.bronze --batch 1 && uv run python -m lakehouse.bronze --batch 1
uv run pytest tests/test_bronze.py -q
```

Running bronze twice is the test, not a typo. Row counts must be unchanged.
Record the suite wall-clock in the progress log from this phase onward.

## Artifacts

- `src/lakehouse/generate.py`, `data/raw/*.csv`
- `data/DEFECTS.md`
- `src/lakehouse/ddl.py`
- `src/lakehouse/bronze/`
- `tests/test_bronze.py`
- `docs/adr/NNNN-<integrity-without-constraints>.md`

## Progress log

Dated appends only. Newest at the bottom.
