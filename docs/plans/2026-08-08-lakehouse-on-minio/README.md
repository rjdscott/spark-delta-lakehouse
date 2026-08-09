# A demonstrable retail banking lakehouse: raw CSV to conformed star schema, on object storage, in a catalog

- **Status:** 🟡 In progress

Supersedes [2026-08-08-phase-1-lakehouse](../2026-08-08-phase-1-lakehouse/),
which sequenced local filesystem first. The stack is now the starting point,
not a later phase.

The thesis is unchanged and is the reason the phases are shaped this way:
medallion is a layering convention, not a modelling methodology. Silver is a
genuinely shared, normalised entity layer with versioned history; gold is
conformed dimensional models built on top. A pipeline count that grows with the
number of consumers rather than the number of business processes is the failure
this repo demonstrates the cure for.

## Scope

In:

- Compose stack: MinIO, Unity Catalog on Postgres, Spark standalone cluster.
- Synthetic retail banking sources as CSV on disk, seeded and deterministic,
  carrying the seven defects from the brief.
- `model/` spec driving DDL, table and column comments, tests and diagrams.
- Bronze, silver with SCD1 and SCD2, gold dimensions and three fact grains.
- A catalog surface someone can browse and query by name, and a demo script
  that walks the whole thing.

Non-goals:

- Databricks and declarative pipelines. Scoped in the README, unbuilt.
- Governance, lineage and access control. Unity Catalog OSS does not provide
  them at a level worth demonstrating, and pretending otherwise would be worse
  than the honest gap recorded in ADR 0004.
- Any orchestration or config framework.

## Status table

| NN | Phase | Status | Last update |
|----|-------|--------|-------------|
| 01 | [Compose stack on MinIO](phase-01-compose-stack-on-minio.md) | 🟢 Completed | 2026-08-08 |
| 02 | [Catalog that survives a restart](phase-02-catalog-that-survives-a-restart.md) | 🟢 Completed | 2026-08-08 |
| 03 | [Sources and seeded defects](phase-03-sources-and-seeded-defects.md) | 🟢 Completed | 2026-08-08 |
| 04 | [Model spec, loader, generated DDL](phase-04-model-spec-and-generated-ddl.md) | 🟡 In progress | 2026-08-08 |
| 05 | [Bronze](phase-05-bronze.md) | 🟢 Completed | 2026-08-08 |
| 06 | [Silver conformed entities](phase-06-silver-conformed-entities.md) | 🟢 Completed | 2026-08-08 |
| 07 | [Silver SCD2 party](phase-07-silver-scd2-party.md) | 🟢 Completed | 2026-08-09 |
| 08 | [Gold star schema](phase-08-gold-star-schema.md) | 🟢 Completed | 2026-08-09 |
| 09 | [The demo](phase-09-the-demo.md) | 🔵 Not started | none |

Phase 02 comes before any data because the catalog choice changes what every
later phase writes into, and because "cataloguing" is half of what this
platform is meant to demonstrate. Phase 07 is separated from 06 because
handwritten SCD2 MERGE is the hardest correctness problem here.

## Critical files

| Path | Holds |
|------|-------|
| `docker/compose.yaml`, `docker/.env` | the stack, and every version with its reason |
| `docker/spark/spark-defaults.conf` | the storage and catalog seam. No pipeline code knows the scheme |
| `model/*.yml` | one spec per entity: grain, keys, history, attributes, relationships |
| `src/lakehouse/catalog.py` | the one module that knows which catalog is in play |
| `src/lakehouse/bronze,silver,gold/` | one module per entity, transformations only |
| `scripts/smoke_stack.py` | proves cluster, catalog, object store and Delta together |

## Top risks

1. **Unity Catalog cannot serve the read path against MinIO.** Confirmed, not
   suspected: three reproduced failures in ADR 0004. Phase 02 decides what the
   catalog actually is, rather than leaving the demo with a gap to talk around.
2. **SCD2 MERGE with intra-day changes and out-of-order arrivals.** MERGE
   permits one action per source row, forcing the union pattern. Phase 07.
3. **As-of resolution at event time.** A transaction posted five days late must
   resolve to the dimension version current at `txn_ts`. Phase 08.
4. **Demo fragility.** A stack that needs three manual `curl` calls before it
   works is a stack that fails in front of an audience. Phase 09 makes the
   whole thing one command from a cold start.
5. **Time.** The full medallion across all entities is the stated goal for the
   day. Phases 03 to 08 are ordered so that stopping after any one of them
   still leaves something demonstrable.

## Decisions this plan implements

- [ADR 0003](../../adr/0003-version-matrix-for-the-local-lakehouse-stack.md),
  the version matrix and why two pins are deliberately not the newest release.
- [ADR 0004](../../adr/0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md),
  the catalog position and what would change to move to Unity Catalog.

ADRs expected during execution. Numbers are claimed at write time:

| Phase | Decision to record |
|-------|--------------------|
| 02 | which catalog the platform actually runs on |
| 04 | spec-driven modelling and its scope limits |
| 05 | integrity enforcement without engine-level constraints |
| 07 | SCD type per entity |
| 08 | surrogate keys, inferred members, snapshot versus derived balances |

## How to resume

Read the status table, open the first phase that is not 🟢, read its progress
log from the bottom. `make stack-up` then `make stack-smoke` confirms the
platform still works before you change anything.
