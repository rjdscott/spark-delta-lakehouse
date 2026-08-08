# 0003. Version matrix for the local lakehouse stack

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

The stack has six components that must agree on Scala binary version, Spark
version, Hadoop version and AWS SDK major version. Getting any one wrong
produces `NoSuchMethodError` or `ClassNotFoundException` at runtime, with a
stack trace that names none of the versions involved. This is the single most
expensive class of mistake in assembling a Spark stack, and the reason the
brief asked for the matrix to be written down.

The instinct is to take the latest release of everything. That instinct is
wrong here, and demonstrably so: the newest Delta and the newest hadoop-aws
both break this stack.

## Options considered

**A. Latest of everything.** Delta 4.3.1, hadoop-aws 3.5.0, Spark 4.1.x.
- Pros: newest fixes, longest support runway.
- Cons: does not work. Delta 4.3.1 compiles against Spark 4.1.0 while the
  Unity Catalog connector compiles against Spark 4.0.0, and hadoop-aws 3.5.0
  does not match the Hadoop the Spark image ships.

**B. Resolve versions from the docs.** Follow the getting-started pages.
- Pros: fast.
- Cons: the UC docs quote a minimum (Spark 3.5.3, Delta 3.2.1) and an example
  using different numbers again. Docs describe a tested combination, not the
  constraint, and they lag the artifacts.

**C. Resolve backwards from the most constrained component, reading POMs.**
Take the UC Spark connector as fixed and derive everything from its published
dependencies and from the Spark image's bundled jars.
- Pros: the constraint is mechanical and checkable rather than remembered.
- Cons: takes an hour up front and has to be redone at each upgrade.

## Decision

**We will pin every version by resolving backwards from
`unitycatalog-spark_2.13`, and record the reason next to each pin in
`docker/.env`.** The connector is the most constrained component in the stack,
so it dictates Scala, Spark and Delta. The Spark image dictates Hadoop, and
Hadoop dictates the AWS SDK.

| Component | Pinned | Determined by |
|-----------|--------|---------------|
| unitycatalog-spark | 0.4.1 | latest published connector, `maven-metadata.xml` |
| Scala | 2.13 | the connector publishes only `_2.13` |
| Spark | 4.0.0 | connector POM: `spark-sql_2.13:4.0.0` |
| delta-spark | 4.1.0 (`delta-spark_4.0_2.13`) | connector POM. **Not 4.3.1**, which needs Spark 4.1.0 |
| Unity Catalog server | 0.5.0 | the image ships it |
| Hadoop | 3.4.1 | bundled in the Spark 4.0.0 image, not chosen |
| hadoop-aws | 3.4.1 | must equal bundled Hadoop. **Not 3.5.0** |
| AWS SDK | 2.24.6 (v2 `bundle`) | `hadoop-project-3.4.1.pom`, `aws-java-sdk-v2.version` |
| Java / Python | 17.0.15 / 3.10.12 | from the image |
| MinIO | RELEASE.2025-09-07T16-13-09Z | pinned, not `latest` |
| Postgres | 16 | Unity Catalog metadata store |

Two pins are deliberately not the newest release, and the reason is recorded
against both, because a future reader will otherwise "fix" them.

One skew is accepted knowingly: the connector compiles against Hadoop 3.4.2
while the runtime supplies 3.4.1. The runtime classpath is what `hadoop-aws`
must match, and Spark's bundled `hadoop-client-api` wins at load time, so
3.4.1 is correct. Similarly the connector declares `software.amazon.awssdk:auth:2.25.37`
as provided while the bundle supplies 2.24.6; `auth` is API-stable across that
range and the stack runs.

Jars are resolved at image build time through Ivy and baked into
`/opt/spark/jars`, rather than fetched by `--packages` at runtime. A demo must
not depend on Maven Central being reachable, and a standalone cluster requires
every node to have an identical classpath.

## Consequences

Upgrading any one component now means re-deriving the matrix rather than
bumping a number, and the derivation is an hour. That cost is the point: it is
paid deliberately at upgrade time instead of accidentally at runtime.

Pinning Delta to 4.1.0 forgoes everything in 4.2 and 4.3, including the Unity
Catalog Delta APIs that Delta 4.3 introduced for catalog-managed tables. That
is a real loss and is the most likely reason to revisit this.

`docker/.env` is now load-bearing documentation. If a version is changed there
without changing the comment, the next reader is misled.

**Revisit when:** a `unitycatalog-spark` release targets Spark 4.1 or later, at
which point Delta 4.3's catalog-managed table support becomes reachable and the
whole matrix should be re-derived from that release.

## Related

- [ADR 0004](0004-spark-session-catalog-until-unity-catalog-can-vend-for-minio.md),
  which records what to do about the part of this stack that does not work.
- `docker/.env`, the executable form of this table.
- `docs/runbooks/run-the-lakehouse-stack.md`, including the failure modes each
  wrong pin produces.
