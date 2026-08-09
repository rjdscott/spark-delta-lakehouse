# Phase 05: Bronze

## Goal

Land the extracts as they arrived and nothing else: append-only, source-shaped,
every column a string, with lineage columns and rescued-data handling. Physical
tables are created from the spec, and the loader refuses to run if a table has
drifted from it.

## Tasks

- [x] `src/lakehouse/catalog.py`: the one module that knows the catalog and the
      storage root. Everything else names a table.
- [x] Spec conformance check, and the loader refuses to load on a mismatch.
      Brought forward from phase 09 per review-03 H-03.
- [x] `src/lakehouse/bronze.py`: read as string, attach `_ingest_ts`,
      `_source_file`, `_batch_id`, capture undeclared columns in
      `_rescued_data`.
- [x] Idempotency by batch through `replaceWhere`.
- [x] MinIO landing zone, so executors can read the extracts.
- [x] `make seed`, `make bronze`, `scripts/verify_bronze.py`.

## Verification

```bash
make generate && make seed && make bronze
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_bronze.py
```

Expected, and unchanged after reloading any batch:

```
bronze.party        total=   5,984   2026-01-15=2,012  2026-02-15=1,986  2026-03-15=1,986
bronze.account      total=   9,500   2026-01-15=3,140  2026-02-15=3,180  2026-03-15=3,180
bronze.transaction  total=  76,296   2026-01-15=28,467  2026-02-15=24,075  2026-03-15=23,754
bronze.party grain from the catalog: One row per party record as it appeared in one source extract, including duplicates.
```

## Artifacts

- `src/lakehouse/catalog.py`, `src/lakehouse/bronze.py`
- `scripts/run_bronze.py`, `scripts/verify_bronze.py`

## Progress log

2026-08-08: Completed. All three batches land, and reloading a batch leaves the
counts identical, so the layer converges rather than grows.

The conformance check earned itself on first contact. `_rescued_data` had been
added to the loader but not declared as a bronze column, and the loader refused
to run: `bronze.account does not match its spec, refusing to load: declared
column '_rescued_data' is missing`. Without it, the write would have failed
later with a Delta metadata mismatch that names no spec and no column, which is
the difference between a check and a stack trace.

Three failures worth keeping:

- `spark-submit` runs a file, not a module, so `src/lakehouse/bronze.py`
  executed directly fails with "attempted relative import with no known parent
  package". `scripts/run_bronze.py` is the thin shim that lets the package stay
  a package.
- The driver had `data/` mounted and the executors did not, so a `file://`
  read failed with `FILE_NOT_EXIST` on a file that plainly existed. The fix is
  the realistic one rather than mounting the directory everywhere: raw extracts
  are uploaded to a landing zone in MinIO, which is what a landing zone is.
- zsh does not word-split unquoted variables, so a `$COMPOSE exec ...` loop
  that works in bash fails with `no such file or directory` naming the whole
  command. Not a repo defect, but it cost time twice.
