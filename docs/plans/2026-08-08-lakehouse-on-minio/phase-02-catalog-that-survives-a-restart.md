# Phase 02: A catalog that survives a restart

## Goal

Decide and build what this platform's catalog actually is, so that
"cataloguing" is something to demonstrate rather than something to apologise
for. Today the pipeline runs on Spark's embedded metastore, which lives inside
the driver container and dies with it. That is fine for a smoke test and wrong
for a demo about modelling and cataloguing.

The decision is between a standalone Hive Metastore, which every engine speaks
and which persists in Postgres, and continuing on Unity Catalog for the
namespace only. It is a real fork with real trade-offs and it gets an ADR.

## Tasks

- [x] Write the ADR: Hive Metastore versus Unity Catalog versus embedded,
      judged on persistence, what the demo can show, and what a bank runs.
- [x] Stand up the chosen catalog in Compose, backed by the existing Postgres
      instance or a sibling database.
- [ ] `src/lakehouse/catalog.py`: the single module that resolves a table name
      to a catalog reference. No transformation code names a catalog or a path.
- [ ] Table and column comments land in the catalog, since they are the payload
      that makes a catalog worth browsing.
- [x] Keep Unity Catalog running and populated so the migration target stays
      visible and honest.
- [x] Re-register the smoke table and confirm it survives
      `make stack-down && make stack-up`.

## Verification

```bash
make stack-smoke
make stack-down && make stack-up
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  -c "spark.sql('SHOW TABLES IN bronze').show()"
```

The table must still be there after the restart. That is the whole point of
the phase.

## Artifacts

- `src/lakehouse/catalog.py`
- catalog service in `docker/compose.yaml`
- an ADR recording the catalog decision

## Progress log

Dated appends only. Newest at the bottom.

2026-08-08: Hive Metastore 4.0.1 on Postgres, chosen over persisting the
embedded metastore because a catalog only one engine can read is not much of a
catalog. ADR 0005. Four failures on the way, all now in the runbook. The
instructive one: Spark's bundled Hive 2.3.10 client calls a thrift method
Hive 4.0.1 removed, so the image now carries Hive 4.0.1's client jars and sets
`spark.sql.hive.metastore.version`. Persistence verified by taking the stack
fully down and back up, after which `bronze.smoke` was still registered with
1000 rows. Remaining in this phase: `src/lakehouse/catalog.py` and getting
table and column comments to land in the catalog, both of which follow the
model spec and so move to phase 04.
