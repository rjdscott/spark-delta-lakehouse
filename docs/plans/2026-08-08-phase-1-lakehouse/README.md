# A reviewer clones the repo, runs one command, and gets a populated lakehouse on local disk

- **Status:** 🔵 Not started

Phase 1 of `docs/initial-prompt.md`: the model spec, the full bronze, silver
and gold layers over a retail banking domain, the tests that prove the
modelling claims, and the docs that let a reader reconstruct why every table is
shaped the way it is. Local filesystem only.

The thesis this executes: medallion is a layering convention, not a modelling
methodology. Silver is a genuinely shared, normalised entity layer with
versioned history; gold is conformed dimensional models built on top. Every
phase below should be traceable to that argument.

## Scope

In:

- `model/` spec, one YAML per entity, driving DDL, tests, diagrams and the
  transformation contracts.
- Bronze append-only ingest, silver conformed entities with SCD1 and SCD2, gold
  dimensions and three fact tables of different grains.
- Synthetic, deterministic, seeded source data across three batch dates, with
  the seven defects from the brief planted in it.
- Pytest suite fast enough to run on every commit.
- README thesis, generated ERD and bus matrix, RUNBOOK.

Non-goals:

- MinIO, `s3a://`, Docker Compose. That is brief phase 2 and gets its own plan.
  This plan only has to avoid foreclosing it, which is what the storage seam in
  phase 01 is for.
- Databricks and declarative pipelines. Brief phase 3, scoped in the README and
  deliberately unbuilt. Do not stub it.
- Any orchestration, config, or plugin framework. The brief is explicit and so
  is `CLAUDE.md`.

## Status table

| NN | Phase | Status | Last update |
|----|-------|--------|-------------|
| 01 | [Foundations and the storage seam](phase-01-foundations-and-storage-seam.md) | 🔵 Not started | none |
| 02 | [Model spec and loader](phase-02-model-spec-and-loader.md) | 🔵 Not started | none |
| 03 | [Sources, seeded defects, bronze](phase-03-sources-and-bronze.md) | 🔵 Not started | none |
| 04 | [Silver conformed entities](phase-04-silver-conformed-entities.md) | 🔵 Not started | none |
| 05 | [Silver SCD2 party](phase-05-silver-scd2-party.md) | 🔵 Not started | none |
| 06 | [Gold dimensions](phase-06-gold-dimensions.md) | 🔵 Not started | none |
| 07 | [Gold facts](phase-07-gold-facts.md) | 🔵 Not started | none |
| 08 | [Generated docs and one-command run](phase-08-docs-and-one-command-run.md) | 🔵 Not started | none |

Ordered by dependency, then by risk. Phase 01 exists this early because the
version matrix is the assumption most likely to be wrong and cheapest to
disprove. Phase 05 is separated from 04 because handwritten SCD2 MERGE with
intra-day versioning is the hardest correctness problem in the repo and should
not share a PR with routine conformance work.

## Critical files

Nothing here exists yet. This is the shape phase 01 commits to and later
phases fill in.

| Path | Holds |
|------|-------|
| `model/*.yml` | one spec per entity: grain, keys, history type, attributes, relationships |
| `src/lakehouse/session.py` | the only module that knows where storage lives |
| `src/lakehouse/spec.py` | spec loading and validation |
| `src/lakehouse/bronze/`, `silver/`, `gold/` | one module per entity, transformations only |
| `tests/` | rules parametrised across specs, not one test per table |
| `warehouse/` | the local Delta root, gitignored |

## Top risks

1. **The JVM version.** This machine runs OpenJDK 25; Spark supports 17 and 21.
   If `delta-spark` and PySpark will not start under it, every later phase is
   blocked on resolving that first. Phase 01 exists to find out on day one, and
   its verification is deliberately "a Delta table appears on disk".
2. **SCD2 MERGE with intra-day changes and out-of-order arrivals.** MERGE
   permits one action per source row, which forces the union pattern. The
   brief plants a party that changes twice in one day and records that arrive
   before versions already loaded. Phase 05, isolated for this reason.
3. **The spec becoming a DSL.** The guardrail is that the spec describes only
   what already varies across the existing entities. A field appearing in
   exactly one spec does not belong in the schema. Phase 02 records this as an
   ADR so later phases have something to be held to.
4. **As-of resolution at event time.** `fact_transaction` must resolve to the
   dimension version current at `txn_ts`, not load time, with inferred members
   for orphan accounts. Phase 07.
5. **Test runtime.** "Fast enough to run on every commit" degrades quietly.
   Every phase from 03 onward reports suite wall-clock in its progress log.

## Decisions this plan implements

- [ADR 0001](../../adr/0001-tiered-docs-scaffold-with-machine-enforcement.md),
  for the docs and `make check` discipline every phase gates on.
- `docs/initial-prompt.md`, which prescribes the modelling outcomes. Where the
  brief names a trade-off, the ADR records why the alternative lost, it does
  not relitigate the choice.

ADRs expected during execution, in roughly this order. Numbers are claimed at
write time, never reserved in advance:

| Phase | Decision to record |
|-------|--------------------|
| 01 | repo structure and the storage seam |
| 02 | spec-driven modelling and its scope limits |
| 03 | integrity enforcement without engine-level constraints |
| 05 | SCD type per entity |
| 06 | surrogate key strategy, hash over identity columns |
| 07 | inferred member handling; snapshot versus derived balances |

## How to resume

Read the status table, open the first phase that is not 🟢, read its progress
log from the bottom. Everything needed is in the phase file.
