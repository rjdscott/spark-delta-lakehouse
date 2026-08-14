# spark-delta-lakehouse

A reference implementation of dimensional modelling on Spark and Delta Lake,
over a retail banking domain. The stack is local and shaped like a small
bank's: MinIO for object storage, a Postgres-backed Hive Metastore as the
catalog, and a Spark standalone cluster that jobs are submitted to. It runs
from cold start with four commands and verifies its own correctness.

```mermaid
flowchart LR
    extracts["Banking extracts"] --> landing[("MinIO landing zone")]
    landing --> bronze["Bronze"]
    bronze --> silver["Silver"]
    silver --> gold["Gold star schema"]
    gold --> queries["Business queries"]
```

## Design

- **Silver is a shared entity layer**: typed, deduplicated, one row per
  business key, with party history kept as SCD Type 2 in timestamp-grained
  effective ranges. Gold builds on silver, never on bronze, so entity logic
  exists once.
- **Grain is declared, not implied.** One YAML spec per entity states the
  grain, business key, history type, and relationships; the DDL, integrity
  tests, ERD, and transformation contracts are generated from it, and a
  loader refuses a table that has drifted from its spec.
- **Facts resolve at event time.** `fact_transaction` joins to the dimension
  version whose effective range contains the transaction's event time. In
  the generated data that changes the answer for 13,247 of 14,899
  transactions relative to a join on the current version.
- **Rebuilds are safe.** Surrogate keys are hashes, batch loads are
  idempotent, and replaying batches in any order converges to the same
  state.

## Documentation

| Page | Covers |
|------|--------|
| [`docs/architecture.md`](docs/architecture.md) | The stack: storage, catalog, compute, submission path |
| [`docs/pipeline.md`](docs/pipeline.md) | Layer semantics, batch execution, verification |
| [`docs/data-model.md`](docs/data-model.md) | Specs, the generated star schema, grains and keys |
| [`docs/scd2.md`](docs/scd2.md) | Party history: ranges, rebuild strategy, event-time joins |
| [`docs/BUS_MATRIX.md`](docs/BUS_MATRIX.md) | Business processes against conformed dimensions, generated |
| [`docs/adr/`](docs/adr/) | Eleven decision records, including two supersessions |
| [`docs/runbooks/`](docs/runbooks/) | Operations, with failure modes from real incidents |
| [`docs/audits/`](docs/audits/) | Seven adversarial reviews, findings reproduced or dropped |
| [`data/DEFECTS.md`](data/DEFECTS.md) | The eight defects seeded into the data on purpose |

The build brief, with scope and phasing, is
[`docs/initial-prompt.md`](docs/initial-prompt.md).

## Running it

Prerequisites: Docker with the compose plugin, `uv`, `make`.

```bash
make stack-up      # MinIO, Hive Metastore, Unity Catalog, Spark master + 2 workers
make generate      # seeded, deterministic banking extracts (with 8 planted defects)
make seed          # upload them to the MinIO landing zone
make demo          # bronze -> silver -> SCD2 -> gold, one batch at a time, narrated
make demo-queries  # business questions answered by name against the star
```

Consoles while it runs: MinIO at `:9001`, Spark master at `:8090`, the
running job at `:4040`. `make help` lists everything, including
`demo-reset`.

## Verification

Verification is scripted, not asserted: `make check` (docs integrity, lint,
unit tests), `make test-spark` (transformation tests, inside the container),
and four `scripts/verify_*.py` checks covering SCD2 range integrity, grain
uniqueness, orphan keys, balance continuity and milestone ordering. The data
carries eight seeded defects, each pinned by a test asserting it is still
planted; a pipeline that only ever sees clean data proves nothing. Lint and
tests run in `make check` locally and in CI on every PR; there is no
pre-commit hook by design.

## Scope and limitations

- **Catalog governance.** Unity Catalog runs in the stack but its credential
  vending cannot reach a non-AWS S3, so the read path runs on the Hive
  Metastore (ADRs
  [0004](docs/adr/0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md),
  [0005](docs/adr/0005-hive-metastore-as-the-working-catalog.md)).
- **Orchestration.** Batches run through `make`; no scheduler, no config
  framework, by design.
- **Databricks.** A declarative-pipelines variant on Unity Catalog volumes is
  scoped in the brief as phase 3 and deliberately unbuilt.
- **Data realism.** The data is internally coherent (a home loan repays, a
  closed account stops transacting) and makes no statistical claim beyond
  that ([ADR 0006](docs/adr/0006-coherence-over-fidelity-in-synthetic-data.md)).
