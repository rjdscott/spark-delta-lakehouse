# Phase 06: Silver conformed entities

## Goal

Silver as a genuinely shared entity layer for everything except party history:
typed, deduplicated on the business key, conformed naming, account as SCD1,
transaction cleansed only. No dimensional resolution, because resolving a
transaction to the dimension version current at its event time is gold's job
and doing it here is the mistake this repo argues against.

Party is deliberately absent. It is SCD2 and lands in phase 07.

## Tasks

- [x] Type coercion from bronze's strings, driven by the spec.
- [x] Deduplication on business key plus sequencing column, with a
      deterministic tiebreak. Not `DISTINCT`.
- [x] Account as SCD1 through a MERGE guarded on the sequencing column.
- [x] Transaction cleansed, no surrogate keys, no joins to dimensions.
- [x] Batch-at-a-time processing rather than a full rebuild.
- [x] `make silver`, `scripts/verify_silver.py`.
- [ ] Hard-deleted parties. Moves to phase 07, where party is built.

## Verification

```bash
make silver
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_silver.py
```

Expected after all three batches:

```
silver.account       rows=  3,165  distinct account_id=  3,165  grain OK
silver.transaction   rows= 75,918  distinct txn_id= 75,918  grain OK
dedupe: bronze distinct accounts=3,165 silver=3,165 OK
coercion: amount=decimal(18,2) txn_ts=timestamp posted_ts=timestamp
orphan account references retained: 0
surrogate keys in silver.transaction: none OK
```

## Artifacts

- `src/lakehouse/silver.py`, `scripts/run_silver.py`, `scripts/verify_silver.py`

## Progress log

2026-08-08: Completed. 3,165 accounts and 75,918 transactions, grain holding on
both, 378 duplicate transaction rows removed without collapsing any distinct
version. Replaying a batch leaves the counts identical, and replaying the
*oldest* batch after the newest leaves the status distribution and the maximum
`updated_at` unchanged, which is the property the sequencing guard exists for:
a late record carrying stale state must not overwrite newer state.

The finding that changed the design: silver was first written as a full rebuild
from all of bronze at once. Every property passed, and
`orphan account references retained: 0` looked like a pass. It was not. Defect
4 withholds forty accounts from the batch 1 extract while batch 1 transactions
already reference them, and rebuilding from all three batches at once makes
those accounts present from the start, so the orphans never exist and gold
would never create an inferred member. A row count cannot tell you that a
defect quietly stopped happening.

Processing batch at a time restores the timeline: after batch 1 alone there are
348 orphan references, and they resolve to zero by batch 3 as the accounts
arrive. That is also how a real pipeline runs, so the fix costs nothing and
buys back a brief requirement.

One environment note: `delta-spark` ships both jars and a Python module. The
jars were baked into the image from the start, but `DeltaTable` lives in the
Python package, which was not installed, so the first run failed with
`ModuleNotFoundError: No module named 'delta'`. It is installed with `--no-deps`
because the package depends on pyspark and would otherwise install a second
copy that disagrees with the image's.
