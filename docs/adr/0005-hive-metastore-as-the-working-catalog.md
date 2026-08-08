# 0005. Hive Metastore as the working catalog

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

[ADR 0004](0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md)
left the platform running on Spark's embedded metastore, which lives in the
driver container and dies with it. That is acceptable for a smoke test and
unacceptable for a platform whose stated purpose is to demonstrate modelling
and cataloguing: restart the stack and the catalog is empty.

The catalog also has to be worth browsing. A catalog is not just a name
resolver; it is where the grain sentence, the column comments and the table
properties live, which is what turns a pile of Delta directories into
something a person can discover.

## Options considered

**A. Persist the embedded metastore on a volume.** Five minutes of work.
- Pros: cheapest possible fix, survives a restart.
- Cons: still single-process and Spark-only. Nothing else can read it, so the
  claim "this is a lakehouse catalog" would be doing a lot of work.

**B. Standalone Hive Metastore backed by Postgres.**
- Pros: the de facto open lakehouse catalog. Spark, Trino, Flink and DuckDB
  all speak thrift to it, so the tables are readable by something other than
  the cluster that wrote them. Persists properly. Holds table and column
  comments and table properties.
- Cons: two more services. Two-level namespace only, so `silver.party` rather
  than `lakehouse.silver.party`. No governance, no lineage.

**C. Keep waiting for Unity Catalog.** Do nothing until vending works.
- Pros: no interim work to unpick.
- Cons: no demonstrable catalog, on someone else's timeline.

## Decision

**We will run the platform on a standalone Hive Metastore backed by Postgres,
and keep Unity Catalog running and populated as the migration target.** Access
goes through one module, so the catalog remains swappable.

Hive Metastore is pinned to 4.0.1, the current release, and Spark is pointed at
its client jars rather than the ones it bundles. See Consequences.

## Consequences

The catalog persists: the stack was taken fully down and brought back up, and
`bronze.smoke` was still registered with its 1000 rows. That is the property
the phase existed to get, and it is now verified rather than assumed.

The tables are readable by any engine that speaks thrift, which is what makes
"catalogue" a real claim rather than a label on Spark's session state.

Three costs, all paid deliberately:

1. **Spark's bundled Hive client cannot talk to this metastore.** Spark 4.0.0
   ships a Hive 2.3.10 client, which calls the thrift method `get_table`. Hive
   Metastore 4.0.1 removed it in favour of `get_table_req`, so every table
   operation failed with `Invalid method name: 'get_table'`. Spark's supported
   remedy is `spark.sql.hive.metastore.version` plus a jar path, so the image
   now carries Hive 4.0.1's client jars alongside Spark's own. This adds about
   200MB to the image and a real risk of classpath conflict at future upgrades.
2. **The metastore needs its own S3 filesystem, on its own version matrix.**
   It creates the warehouse directory itself, so it needs `hadoop-aws`. Its
   Hadoop is 3.3.6, which uses AWS SDK v1, while Spark's Hadoop 3.4.1 uses v2.
   The stack therefore runs two different AWS SDK majors in two different JVMs,
   which is correct: the version matrix is per process, not per platform.
3. **Two-level namespace.** `silver.party`, not `lakehouse.silver.party`. The
   three-level namespace is one of the things Unity Catalog would bring.

The Databricks-shaped part of the demo is now explicitly the part that is not
running. That is a better position than before, when it was implicitly so.

**Revisit when:** Unity Catalog can vend credentials for a non-AWS S3, at which
point ADR 0004's migration applies and this metastore becomes redundant, or
when a Spark release bundles a Hive client new enough to drop the jar override.

## Related

- [ADR 0003](0003-version-matrix-for-the-local-lakehouse-stack.md), extended
  here with a second, independent matrix for the metastore process.
- [ADR 0004](0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md),
  which this supersedes in practice for the read path while leaving its Unity
  Catalog findings intact.
- `docs/runbooks/run-the-lakehouse-stack.md` for the failure modes.
