# spark-delta-lakehouse: build brief

Hand this to Claude Code. It states the intent, the constraints and the acceptance criteria. Structural decisions are deliberately left open.

---

## Brief

Build `spark-delta-lakehouse`: a reference implementation of dimensional modelling on Spark and Delta Lake, using a retail banking domain. It will be a public GitHub repo and is intended to be read as much as run, so the quality bar is a repo someone reviews and immediately understands the reasoning behind.

You own the structure. Do not ask me to approve a file layout before starting. Decide it, justify it in an ADR, and build.

### The thesis the repo argues

Medallion architecture is a layering convention, not a modelling methodology. Teams that adopt bronze/silver/gold without dimensional discipline end up with pipeline counts that scale with the number of consumers instead of the number of business processes, because every new request rebuilds entity logic from bronze rather than reusing a conformed layer.

This repo demonstrates the corrective: silver as a genuinely shared, normalised entity layer with properly versioned history, and gold as conformed dimensional models built on top. Every design decision should be traceable to that argument. The README makes the case in under 400 words, without evangelism.

### Phasing

Build in this order. Do not start a phase before the previous one runs and its tests pass.

**Phase 1 is the deliverable.** Phases 2 and 3 are extensions that must not require rewriting phase 1.

| Phase | Scope | Storage |
|---|---|---|
| 1 | Model spec, full bronze/silver/gold, tests, docs, ADRs | Local filesystem |
| 2 | Docker Compose with MinIO | `s3a://` |
| 3 | Databricks Free Edition and declarative pipeline variant | Unity Catalog volumes |

Phase 3 is scoped in the README and left unbuilt for now. Do not stub it, do not scaffold for it. Just make sure nothing in phase 1 forecloses it.

### The model spec (the core idea)

Local Delta gives you tables and a transaction log. It does not give you a catalog that knows what a dimension is. So the model is declared in the repo as data, and the engine is a target.

A `model/` directory holds one YAML file per entity, declaring: layer, kind (dimension, fact, or entity), grain as a sentence, business key, surrogate key strategy, history type and sequencing column, attributes with tracked/untracked flags, and relationships.

That spec drives four things, which is what makes this modelling rather than documentation:

1. **DDL generation.** Delta table creation, column comments, table properties. Physical tables are derived, never handwritten.
2. **Test generation.** Grain uniqueness, SCD2 non-overlap, referential integrity and nullability all fall out of the spec. One test per rule, parametrised across specs, not one test per table.
3. **Diagram generation.** Mermaid ERD from the relationships, and `docs/BUS_MATRIX.md` from which facts reference which dimensions. Docs that cannot drift from code.
4. **Transformation contracts.** The SCD2 builder reads `history.type` and `sequence_by` from the spec rather than hardcoding them, so adding an entity means adding a spec, not copying a module.

**The guardrail, and I mean this:** the spec describes only what already varies across the existing entities. No inheritance, no macros, no expression language, no plugin registry. If a field appears in exactly one spec, it does not belong in the schema. This is a declarative model, not a homegrown framework, and the difference is discipline about scope. If you find yourself building a DSL, stop and write the logic directly instead.

### Storage seam

One environment variable, `STORAGE_ROOT`, resolving to `./warehouse` in phase 1 and `s3a://lakehouse` in phase 2. Nothing in the codebase outside the session builder and one config value may know which is in play.

This is the acceptance test for the whole abstraction. If adding MinIO in phase 2 requires touching transformation code, the design was wrong. Prove it by writing phase 1 so the switch is a one-line change.

### Domain

Retail banking: parties, accounts, transactions. Three CSV sources across three sequential batch dates so incremental behaviour is exercised rather than asserted. Generate synthetically and deterministically, seeded so runs reproduce.

- **party**: `party_id`, `full_name`, `address_line`, `suburb`, `state`, `postcode`, `risk_rating`, `segment`, `updated_at`. Roughly 2000 rows.
- **account**: `account_id`, `party_id`, `product_type`, `open_date`, `close_date`, `status`, `updated_at`. Roughly 3000 rows.
- **transaction**: `txn_id`, `account_id`, `txn_ts`, `posted_ts`, `amount`, `currency`, `merchant_category`, `txn_type`. Roughly 50000 rows.

### Seeded defects (non-negotiable)

The generator plants these and the pipelines handle them. Document each in `data/DEFECTS.md` with the specific behaviour it exercises.

1. Exact duplicate rows in every source
2. A party whose address changes twice within the same day, forcing intra-day SCD2 versioning
3. Records arriving out of sequence, where `updated_at` predates a version already loaded
4. Transactions in batch 1 referencing `account_id` values that first appear in batch 2
5. Transactions with `posted_ts` up to 5 days after `txn_ts`
6. Nulls in `risk_rating` and `merchant_category`
7. Parties hard deleted between batches: present in batch 1, absent in batch 2

### Modelling requirements

Build these fully. Where a genuine trade-off exists, pick one, implement it, and record the alternative in an ADR.

**Bronze**: append-only, source-shaped, with `_ingest_ts`, `_source_file`, `_batch_id`. No dedupe, no renaming, no business logic. Rescued-data handling for unexpected columns.

**Silver**: deduplication on business key, type coercion, conformed naming. Party as SCD Type 2 via handwritten MERGE, including the union pattern required because MERGE permits only one action per source row. Account as SCD Type 1. Transaction cleansed only, no dimensional resolution.

**Gold**:

- `dim_party`: hash surrogate keys from business key plus `effective_from`, not identity columns, so keys are stable across environments and reprocessing
- `dim_account`, `dim_date`, `dim_merchant_category`
- `fact_transaction`: transaction grain, resolved to the dimension version current at `txn_ts` via an as-of join on the effective range, with inferred member handling for orphan account references
- `fact_daily_balance`: periodic snapshot, one row per account per day
- `fact_account_lifecycle`: accumulating snapshot with multiple milestone dates updated in place

Grain is declared in the spec, echoed in the docstring, and written into the Delta table comment.

### Tests

Pytest, fast enough to run on every commit.

- Idempotency: each layer re-run produces identical row counts and content hashes
- SCD2 integrity: no overlapping effective ranges per business key, exactly one current row per key, no timeline gaps
- Grain uniqueness on every fact table
- Referential integrity: zero orphan surrogate keys
- Temporal correctness: a late-posted transaction resolves to the dimension version current at event time, not load time
- Out-of-order resilience: replaying batches in the wrong order converges to the same final state
- Spec conformance: every physical table matches its declared spec

### Phase 2: Docker and MinIO

Compose with three services: MinIO, a short-lived `mc` init container that creates the bucket, and the Spark app container running `local[*]`.

**No Spark standalone cluster.** No master, no workers. At this data volume it is ceremony, it triples the failure surface, and it teaches nothing about modelling.

The point of MinIO is that object stores have no atomic rename, so Delta commits route through the LogStore rather than a filesystem move. Confront that, plus path-style access, endpoint and credential config, and the committer question.

Pin every JAR version explicitly: `hadoop-aws` must match the Hadoop version bundled with the Spark build, `aws-java-sdk-bundle` must match `hadoop-aws`, and `delta-spark` must match Spark. Mismatches produce unhelpful `NoSuchMethodError` traces. Write an ADR recording the matrix and why each version was chosen.

Phase 1 must still run with `pip install -r requirements.txt` and no Docker.

### Documentation

- `README.md`: the thesis, what the repo demonstrates, how to run each phase, honest scope statement including what phase 3 would add
- Mermaid diagrams: layer flow, star schema ERD, and an SCD2 timeline for the worked same-day-change example
- `docs/BUS_MATRIX.md`: business processes against conformed dimensions, generated from the specs
- `docs/adr/`: numbered ADRs, roughly eight to twelve. At minimum: spec-driven modelling and its scope limits, surrogate key strategy, SCD type per entity, snapshot versus derived balances, the storage seam, integrity enforcement without engine-level constraints, inferred member handling, JAR version matrix, and why no Spark cluster.
- `RUNBOOK.md`: execution order per phase, and what to inspect after each step to confirm it worked

ADRs use context, decision, consequences. Consequences state what the decision costs, not only what it buys.

### Repo furniture

GitHub Actions running lint and tests. Pre-commit with ruff. Packaging sufficient for clean imports. Make targets for the common tasks. Keep this layer thin: invisible until needed.

### Constraints on how you work

- Minimal and clean over comprehensive. No abstraction that does not currently earn its keep. No orchestration framework, no config framework, no plugin system.
- Run the code. Do not deliver anything that has not executed successfully.
- Build and verify one layer at a time, in dependency order.
- Comments explain why, not what. Where you chose between viable options, name the other in one line and point at the ADR.
- Write for a staff or principal engineer reading cold. Assume Spark and SQL fluency, do not assume dimensional modelling fluency.
- No em-dashes anywhere in code, comments or documentation.

### Definition of done for phase 1

A reviewer clones the repo, runs one command, and gets a populated lakehouse on local disk. They read the README and ADRs and reconstruct why every table is shaped the way it is. Nothing requires verbal explanation.

Start by stating your plan in ten lines or fewer, including proposed structure, the spec schema, and your ADR list. Then build phase 1.