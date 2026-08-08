# Phase 01: Compose stack on MinIO

## Goal

A Spark standalone cluster writing Delta tables into MinIO, with Unity Catalog
running on Postgres, reproducible from a cold start by one command, and every
version pinned with the reason recorded.

## Tasks

- [x] Derive the version matrix backwards from the Unity Catalog Spark connector.
- [x] Compose stack: MinIO, mc bucket init, Postgres, Unity Catalog, Spark
      master, two workers, driver container.
- [x] One Spark image for every node, jars resolved at build time and baked in.
- [x] Back Unity Catalog with Postgres rather than its default H2.
- [x] `make stack-up`, `stack-down`, `stack-destroy`, `stack-ps`, `stack-logs`,
      `stack-smoke`, `stack-shell`.
- [x] Smoke test proving cluster, catalog, object store and Delta together.
- [x] ADR 0003 for the version matrix, ADR 0004 for the catalog position.
- [x] Runbook carrying every failure mode hit, with exact error strings.

## Verification

```bash
make stack-up
make stack-smoke
```

Expected:

```
spark version        : 4.0.0
master               : spark://spark-master:7077
rows via catalog     : 1000
tables in bronze     : ['smoke']
executors registered : 2
```

## Artifacts

- `docker/compose.yaml`, `docker/.env`, `docker/spark/`, `docker/uc/`
- `scripts/smoke_stack.py`
- ADRs 0003 and 0004, `docs/runbooks/run-the-lakehouse-stack.md`

## Progress log

2026-08-08: Completed. Nine distinct failures on the way, all recorded in the
runbook. The three that cost the most time: Unity Catalog rejects the `s3a`
scheme and then rejects its own bucket config without an STS role ARN and then
vends credentials MinIO refuses with a 403, which together ended the attempt to
put UC on the read path; Spark 4 creates an `artifacts/` directory in the
working directory at session start and fails as the unprivileged user; and
Delta needs `spark_catalog` wrapped as `DeltaCatalog` independently of the SQL
extension. `make stack-smoke` green: 1000 rows, 2 executors, `_delta_log`
present in MinIO.
