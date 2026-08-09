# 0004. Spark session catalog until Unity Catalog can vend for MinIO

- **Status:** Superseded by [0005](0005-hive-metastore-as-the-working-catalog.md)
- **Date:** 2026-08-08

## Context

The goal is a local stack that resembles Databricks closely enough that
pipelines and SQL move across unchanged, which means Unity Catalog holding a
three-level `catalog.schema.table` namespace over Delta tables in object
storage.

Unity Catalog 0.5.0 runs locally and works: it starts, it is backed by
Postgres rather than its default H2, and `lakehouse.bronze`, `lakehouse.silver`
and `lakehouse.gold` were created through its REST API. What does not work is
reading or writing those tables from Spark when the storage is MinIO.

Every table access through the UC catalog calls
`generateTemporaryPathCredentials`. Three attempts, three distinct failures,
each one reproduced against the running stack:

1. Location registered as `s3a://` returns
   `400 INVALID_ARGUMENT: Unsupported URI scheme: s3a`. UC accepts only `s3`.
2. Location as `s3://` with `s3.bucketPath.0` configured but no role ARN
   returns `400 FAILED_PRECONDITION: S3 bucket configuration not found`. The
   entry is not considered valid without the AWS STS role.
3. Role ARN and a placeholder session token set, so UC returns static
   credentials without calling STS, and MinIO rejects them: `403` on
   `getFileStatus` for `_delta_log/_last_checkpoint`, because MinIO validates
   session tokens and this one was never issued by its STS.

The root cause is structural, not a misconfiguration. UC 0.5.0's S3 config
exposes `bucketPath`, `region`, `awsRoleArn`, `accessKey`, `secretKey` and
`sessionToken`, and **no endpoint field**. Credential vending is built around
AWS STS. There is no supported way to point it at a non-AWS S3, which matches
the still-open upstream discussion on custom S3 endpoints.

## Options considered

**A. Wait for UC to support custom S3 endpoints.** Build nothing until then.
- Pros: the eventual architecture is the intended one.
- Cons: no working pipeline today, on an upstream timeline we do not control.

**B. Mint real MinIO STS credentials and feed them to UC.** MinIO can issue
temporary credentials via AssumeRole; an init step could write them into
`server.properties`.
- Pros: keeps UC on the read path, closest to the Databricks shape.
- Cons: the credentials expire, so the stack acquires a refresh mechanism and a
  new failure mode that appears hours later, which is the worst kind for a
  demo. Also unproven: UC would still have to accept a non-AWS STS issuer.

**C. Use the Spark session catalog for the pipeline, keep UC for the
namespace.** Tables are created in `spark_catalog` against `s3a://` locations
with Spark authenticating to MinIO directly; UC stays running and populated so
the catalog layer is real and demonstrable.
- Pros: works today, proven end to end. The pipeline code is unchanged when UC
  becomes viable, because the catalog is reached through one module.
- Cons: `SELECT * FROM lakehouse.gold.fact_transaction` does not run against
  UC, so the most Databricks-like part of the demo is the part that is
  simulated. The three-level namespace is registered but not on the read path.

**D. Drop UC and MinIO, run Delta on the local filesystem.** The brief's
original phase 1.
- Pros: simplest, fewest components.
- Cons: abandons the object-store behaviour that is the whole point of running
  MinIO, and the stated goal of resembling a bank's platform.

## Decision

**We will run the pipeline through the Spark session catalog against
`s3a://` on MinIO, and keep Unity Catalog running and populated as the catalog
layer we migrate to.** Access to the catalog goes through one module, so the
migration is a configuration change rather than a rewrite.

Concretely: `spark.sql.defaultCatalog=spark_catalog`, with the `lakehouse` UC
catalog fully configured alongside it. Moving over is a one-line change to that
property once vending works.

## Consequences

There is a working lakehouse today: a Spark standalone cluster, Delta tables in
MinIO, SQL by name over `bronze`, `silver` and `gold`. The smoke test proves
it, and `make stack-smoke` reproduces the proof.

The demo has an honest gap that must be narrated rather than hidden. Unity
Catalog is up, has the namespace, and is not on the read path. Anyone shown
this stack should be told that, because the alternative is someone later
discovering it and doubting the rest.

Governance, lineage and permissions do not arrive with this decision. They were
not going to arrive from UC OSS either, but the gap is now explicit.

Storing table metadata in Spark's embedded metastore means it lives in the
driver container. Destroying the stack loses the table registrations, though
not the data: the Delta logs in MinIO are the durable record and tables can be
re-registered from their locations.

**Revisit when:** Unity Catalog gains an S3 endpoint configuration, or a
release supports credential vending against a non-AWS S3. At that point the
change is `spark.sql.defaultCatalog` and re-registering the tables as external
in UC.

## Related

- [ADR 0003](0003-version-matrix-for-the-local-lakehouse-stack.md), the version
  matrix this stack runs on.
- `docs/runbooks/run-the-lakehouse-stack.md`, which carries all three vending
  failures as documented failure modes with their exact error strings.
- Upstream discussion on custom S3 endpoints:
  https://github.com/unitycatalog/unitycatalog/discussions/890
