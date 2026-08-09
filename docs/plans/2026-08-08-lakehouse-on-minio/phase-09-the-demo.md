# Phase 09: The demo

## Goal

One command that walks the whole lakehouse from cold, one batch at a time,
narrating what each layer did. Advancing a batch at a time is not presentation
polish: it is the only way the seeded defects mean anything, because a
late-arriving account is only late if the batches arrive in order.

## Tasks

- [x] `scripts/demo.py`, driving bronze, silver, SCD2 and gold per batch.
- [x] `make demo`, `make demo-queries`, `make demo-reset`.
- [x] Unknown-party member, closing the 294 null foreign keys from phase 08.
- [x] Inferred members exercised: 37 appear at batch 1 and reconcile by batch 2.
- [x] `scripts/demo_queries.py`, four business questions answered by name.
- [x] Clean run: no stack traces on screen.

## Verification

```bash
make stack-up
make generate && make seed
make demo-reset && make demo
make demo-queries
```

Expected: the batch narration below, then every verification green.

```
BATCH 1  dim_account  3,162 (37 inferred)
  inferred member: A003128 is referenced by transactions but its account
  record has not arrived yet
BATCH 2  dim_account  3,165 (0 inferred)   silver.party 25 closed as deleted
BATCH 3  fact_transaction 75,918   fact_daily_balance 288,310

14,644 transactions belong to a party that changed.
12,967 of them resolved to a version that is NOT the current one.
```

## Artifacts

- `scripts/demo.py`, `scripts/demo_queries.py`, `scripts/reset.py`
- `demo`, `demo-queries`, `demo-reset` targets

## Progress log

2026-08-09: Completed. The demo runs from cold with no stack traces, and both
gaps left open by phase 08 are closed: null foreign keys are zero, and inferred
members are demonstrated rather than merely implemented.

Getting to a clean run took four attempts, and the sequence is worth keeping
because each failure disguised the next:

1. **Executors OOM-killed, exit 137.** Spark recovered by re-running the stage,
   so the job succeeded while printing `MetadataFetchFailedException` traces. A
   recovered failure still looks like a failure to an audience, and the exit
   code in the worker log is the only place the truth appears.
2. **More memory did not fix it,** which was the useful signal: the problem was
   the plan, not the heap. `fact_daily_balance` joined accounts to dates on a
   range condition, and a non-equi join is a nested loop. Replaced with a
   per-account `sequence()`, which needs no join at all.
3. **Still failing,** because a 288,000 row fully recomputed fact was being
   written with MERGE plus a not-matched-by-source scan. A fact rebuilt from
   silver every run is an overwrite. Dimensions still merge, because a
   surrogate key must survive a rebuild, and so does the accumulating snapshot,
   whose entire point is that a row is revisited rather than replaced.
4. **`DELTA_FAILED_TO_MERGE_FIELDS: Failed to merge fields 'movement' and
   'movement'`.** `sum()` of `decimal(18,2)` widens to `decimal(28,2)`. MERGE
   had been casting it back implicitly; an overwrite does not. The error names
   the column twice and the types not at all.

The general lesson: Spark's fault tolerance is good enough to hide a design
problem as a transient one. A retried stage is not a healthy stage.
