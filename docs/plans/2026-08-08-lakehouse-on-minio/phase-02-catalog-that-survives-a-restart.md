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

- [ ] Write the ADR first: Hive Metastore versus Unity Catalog versus embedded,
      judged on persistence, what the demo can show, and what a bank runs.
- [ ] Stand up the chosen catalog in Compose, backed by the existing Postgres
      instance or a sibling database.
- [ ] `src/lakehouse/catalog.py`: the single module that resolves a table name
      to a catalog reference. No transformation code names a catalog or a path.
- [ ] Table and column comments land in the catalog, since they are the payload
      that makes a catalog worth browsing.
- [ ] Keep Unity Catalog running and populated so the migration target stays
      visible and honest.
- [ ] Re-register the smoke table and confirm it survives
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
