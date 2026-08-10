# spark-delta-lakehouse

Dimensional modelling on Spark and Delta Lake, over a retail banking domain,
on a local stack shaped like a small bank's: MinIO for object storage, a
Postgres-backed Hive Metastore as the catalog, and a Spark standalone cluster
that jobs are submitted to. Built to be read as much as run; the build brief is
[`docs/initial-prompt.md`](docs/initial-prompt.md).

## The thesis

Medallion architecture is a layering convention, not a modelling methodology.
Bronze, silver and gold say where data sits and how refined it is. They say
nothing about what a row means, how an entity keeps history, or which keys a
fact should carry. Teams that adopt the layers without dimensional discipline
end up with pipeline counts that scale with the number of consumers instead of
the number of business processes, because every new request rebuilds entity
logic from bronze.

This repo demonstrates the corrective. Silver is a genuinely shared entity
layer: typed, deduplicated, one row per business key, with party history kept
as SCD Type 2 in timestamp-grained effective ranges. Gold is conformed
dimensional models built on silver and never on bronze: hash surrogate keys
that survive a rebuild, and three fact tables at three deliberately different
grains, because grain is a choice, not a consequence.

The claim is measurable in the data this repo generates. Of the 14,644
transactions belonging to a customer whose attributes changed, **12,967
resolve to a dimension version that is not the current one**, because
`fact_transaction` joins to the version whose effective range contains the
transaction's event time. A pipeline that joins to "the current row" answers
every one of those differently, and wrongly, and nobody notices, because the
join succeeds.

The model is declared, not implied. One YAML per entity in
[`model/`](model/) states the grain as a sentence, the business key, the
history type and sequencing column, tracked attributes, and relationships.
Four things are generated from it: the DDL (grain lands in the table comment,
readable from the catalog), the integrity tests, the diagrams below, and the
transformation contracts (the SCD2 builder reads `history.type` from the spec
rather than hardcoding it). A loader refuses to run against a table that has
drifted from its spec. The discipline that keeps this from becoming a
framework: the spec describes only what already varies across existing
entities, and a field used by exactly one spec does not belong in the schema.

## The star

Generated from the specs by `make docs`; `make check` fails if it drifts.

<!-- erd:start -->
```mermaid
erDiagram
    fact_account_lifecycle }o--|| dim_account : "account_sk"
    fact_account_lifecycle }o--|| dim_date : "opened_date_key"
    fact_daily_balance }o--|| dim_account : "account_sk"
    fact_daily_balance }o--|| dim_date : "date_key"
    fact_transaction }o--|| dim_party : "party_sk"
    fact_transaction }o--|| dim_account : "account_sk"
    fact_transaction }o--|| dim_merchant_category : "merchant_category_sk"
    fact_transaction }o--|| dim_date : "date_key"
    dim_account {
        grain "One row per account, carrying its latest known state"
    }
    dim_date {
        grain "One row per calendar day across the range the facts require"
    }
    dim_merchant_category {
        grain "One row per merchant category, including a member for transactions that carry none"
    }
    dim_party {
        grain "One row per party per version of its tracked attributes, effective over a timestamp range"
    }
    fact_account_lifecycle {
        grain "One row per account, carrying its milestone dates, updated in place as each milestone occurs"
    }
    fact_daily_balance {
        grain "One row per account per calendar day the account was open, whether or not it transacted"
    }
    fact_transaction {
        grain "One row per transaction event, resolved to the dimension versions current at the moment it occurred"
    }
```
<!-- erd:end -->

The bus matrix, also generated, is
[`docs/BUS_MATRIX.md`](docs/BUS_MATRIX.md).

## Running it

Prerequisites: Docker with the compose plugin, `uv`, `make`.

```bash
make stack-up      # MinIO, Hive Metastore, Unity Catalog, Spark master + 2 workers
make generate      # seeded, deterministic banking extracts (with 7 planted defects)
make seed          # upload them to the MinIO landing zone
make demo          # bronze -> silver -> SCD2 -> gold, one batch at a time, narrated
make demo-queries  # business questions answered by name against the star
```

Consoles while it runs: MinIO at `:9001`, Spark master at `:8090`, the running
job at `:4040`. `make help` lists everything, including `demo-reset`.

Verification is scripted, not asserted: `make check` (docs integrity, lint,
unit tests), `make test-spark` (transformation tests, inside the container),
and four `scripts/verify_*.py` checks covering SCD2 range integrity, grain
uniqueness, orphan keys, balance continuity and milestone ordering. The data
carries seven seeded defects ([`data/DEFECTS.md`](data/DEFECTS.md)); a
pipeline that only ever sees clean data proves nothing.

## What this is not

- **Not governed.** Unity Catalog runs in the stack and holds a namespace, but
  its credential vending cannot reach a non-AWS S3, so the read path runs on
  the Hive Metastore. Recorded, with the three reproduced failures, in ADRs
  [0004](docs/adr/0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md)
  and [0005](docs/adr/0005-hive-metastore-as-the-working-catalog.md).
- **Not orchestrated.** Batches run through `make`. No scheduler, no config
  framework, on purpose.
- **Not Databricks.** A declarative-pipelines variant on Unity Catalog volumes
  is scoped in the brief as phase 3 and deliberately unbuilt; nothing here
  forecloses it.
- **Not statistically realistic.** The data is internally coherent (a home
  loan repays, a closed account stops transacting) and makes no claim beyond
  that ([ADR 0006](docs/adr/0006-coherence-over-fidelity-in-synthetic-data.md)).

## Where the reasoning lives

| | |
|---|---|
| [`docs/adr/`](docs/adr/) | ten decisions, including two honest supersessions |
| [`docs/audits/`](docs/audits/) | six adversarial reviews, findings reproduced or dropped |
| [`docs/runbooks/`](docs/runbooks/) | operations, with failure modes from real incidents |
| [`docs/plans/`](docs/plans/) | the phase plans, progress logs included |
| [`data/DEFECTS.md`](data/DEFECTS.md) | what is wrong with the data on purpose |

The audits are part of the material: the most instructive defect in the repo,
a replay order that silently resurrected 25 deleted customers past a green
convergence proof, is written up in
[review-06](docs/audits/2026-08-09-review-06/00-executive-summary.md) with its
reproduction and fix ([ADR 0010](docs/adr/0010-deletion-derives-from-the-snapshot-stream.md)).
