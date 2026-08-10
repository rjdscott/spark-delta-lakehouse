# Run the local lakehouse stack

## When to use

Starting, demonstrating, or debugging the Docker Compose lakehouse: MinIO for
object storage, a Postgres-backed Hive Metastore as the working catalog, a
Unity Catalog server (namespace only; see ADR 0005), and a Spark standalone
cluster with two workers. Covers bringing the stack up, running the full
pipeline, verifying it, and shutting down.

## Steps

1. Confirm the Docker CLI is pointed at a running daemon. On a machine with
   Docker Desktop installed but not started, the CLI targets a socket that does
   not exist while the system daemon runs fine:

   ```bash
   docker context ls          # look for the ERROR column
   docker context use default # the system daemon at /var/run/docker.sock
   docker version --format 'server {{.Server.Version}}'
   ```

2. Bring the stack up. First run builds the Spark image, which resolves the
   jar matrix through Ivy and takes a few minutes; it also generates
   `docker/hive/core-site.xml` from its template using the credentials in
   `docker/.env`. Later runs are cached:

   ```bash
   make stack-up
   make stack-ps
   ```

   Expected, all eight services: `catalog-db`, `hive-db`, `hive-metastore`,
   `minio` and `unitycatalog` healthy; `spark-master`, `spark-worker-1`,
   `spark-worker-2` and `app` up; `minio-init` exited 0.

3. Prove every seam before touching real data:

   ```bash
   make stack-smoke
   ```

   Expected output ends with:

   ```
   rows via catalog     : 1000
   tables in bronze     : ['smoke']
   executors registered : 2
   ```

   `executors registered : 2` is the line that matters: the job ran on the
   workers, not in the driver. The table registration survives
   `make stack-down && make stack-up`, because the metastore is Postgres.

4. Generate the source extracts and land them in the MinIO landing zone:

   ```bash
   make generate   # seeded, deterministic; 7 planted defects (data/DEFECTS.md)
   make seed
   ```

5. Run the pipeline, one batch at a time, narrated:

   ```bash
   make demo
   ```

   Roughly ten minutes on a workstation. Watch for: 37 inferred members at
   batch 1 reconciling to 0 at batch 2, 25 parties closed as deleted at
   batch 2, and the closing block reporting how many facts resolved to a
   non-current dimension version. To rerun from cold: `make demo-reset` first.
   Individual layers: `make bronze`, `make silver`, `make party`, `make gold`.

6. Verify. Unit and docs checks on the host, transformation tests in the
   container, integrity checks against the live tables:

   ```bash
   make check
   make test-spark
   docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
     /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_scd2.py
   ```

   Same invocation for `verify_bronze.py`, `verify_silver.py`,
   `verify_gold.py` and `demo_queries.py`. Every count in `verify_scd2`
   (overlaps, gaps, inverted ranges, keys with more than one current row)
   must be zero; `keys with 0 current : 25` is the deleted parties and is
   correct.

7. The visual surfaces, for demonstrating:

   | URL | Shows |
   |-----|-------|
   | http://localhost:9001 | MinIO console. Watch `_delta_log` grow per commit |
   | http://localhost:8090 | Spark master. Workers, cores, running applications |
   | http://localhost:4040 | The job UI, only while a job is running |
   | http://localhost:8080 | Unity Catalog REST API |

   Unity Catalog holds the `lakehouse.bronze/silver/gold` namespace but is
   not on the read path; the pipeline's catalog is the Hive Metastore. Why,
   with the three reproduced vending failures, is ADR 0004; the decision to
   run on the metastore is ADR 0005.

8. Shut down. `stack-down` keeps the data and the catalog, `stack-destroy`
   deletes the volumes too:

   ```bash
   make stack-down
   make stack-destroy
   ```

## Failure modes

All of these were hit while building the stack on 2026-08-08. The error
strings are quoted exactly, because they are what you will search for.

- **`failed to connect to the docker API at unix:///home/<user>/.docker/desktop/docker.sock`.**
  The CLI context points at Docker Desktop, which is not running. The system
  daemon is usually running anyway. `docker context use default`. Note the two
  daemons keep separate image stores, so images pulled under one are invisible
  to the other.

- **`app` never starts and `unitycatalog` sits at `health: starting` forever.**
  The healthcheck is failing. The UC image ships neither `curl` nor `wget`, so
  an HTTP probe cannot work. A bash `/dev/tcp` probe is correct, but must be
  invoked as `["CMD", "bash", "-c", ...]`: under `CMD-SHELL` it runs in `sh`
  and fails with `can't create /dev/tcp/localhost/8080: nonexistent directory`,
  because `/dev/tcp` is a bash builtin rather than a real path.

- **`java.nio.file.AccessDeniedException: /opt/lakehouse` before any job runs.**
  Spark 4 creates an `artifacts/` directory relative to the working directory
  at session start. The image runs as the unprivileged `spark` user, so the
  working directory must be chowned to it in the Dockerfile.

- **`ApiException: generateTemporaryPathCredentials call failed with: 400 ... "Unsupported URI scheme: s3a"`.**
  Unity Catalog accepts `s3://` only. Spark reads it through the s3a connector
  via `fs.s3.impl=org.apache.hadoop.fs.s3a.S3AFileSystem`.

- **`400 FAILED_PRECONDITION ... "S3 bucket configuration not found."`**
  UC will not treat an `s3.bucketPath.N` entry as usable without an AWS STS
  role ARN, even when access key and secret are set.

- **`403` on `getFileStatus ... _delta_log/_last_checkpoint` from MinIO.**
  UC vended credentials including a session token that MinIO's STS never
  issued, so MinIO rejects them. This is the end of the road for UC credential
  vending against MinIO; see ADR 0004. The stack runs the pipeline through the
  Spark session catalog instead.

- **`[DELTA_CONFIGURE_SPARK_SESSION_WITH_EXTENSION_AND_CATALOG]` on a path
  write.** `spark.sql.extensions` alone is not enough. Delta also needs
  `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`.
  Configuring the Unity Catalog catalog does not cover this: they are two
  different catalogs.

- **`Invalid method name: 'get_table'` from the metastore.** Spark 4.0.0 ships
  a Hive 2.3.10 metastore client; Hive Metastore 4.0.1 removed that thrift
  method in favour of `get_table_req`. Point Spark at newer client jars with
  `spark.sql.hive.metastore.version=4.0.1` and
  `spark.sql.hive.metastore.jars.path=file:///opt/hive-metastore-jars/*`. The
  image carries Hive 4.0.1's jars for this reason.

- **`ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem` from the
  metastore, not from Spark.** The metastore creates the warehouse directory
  itself, so it needs `hadoop-aws` too. Match it to *Hive's* Hadoop (3.3.6,
  AWS SDK v1), not Spark's (3.4.1, AWS SDK v2). Two SDK majors in one stack is
  correct; they are separate JVMs.

- **`Failed to create external path s3a://...` from the metastore, with the
  s3a jars present.** Hadoop's `Configuration` reads XML from the classpath and
  ignores JVM system properties, so `-Dfs.s3a.endpoint` passed through
  `SERVICE_OPTS` silently does nothing. The settings must be in
  `docker/hive/core-site.xml`.

- **`curl` fails with exit code 127 building the Hive image.** The Hive image
  ships no download tool. Fetch in a separate build stage that has one.

- **A Spark job fails with `NoSuchMethodError` or `ClassNotFoundException`
  naming an AWS or Hadoop class.** The jar matrix is wrong. Do not bump
  versions to fix it; re-derive them per ADR 0003. `hadoop-aws` must equal the
  Hadoop bundled in the Spark image exactly:

  ```bash
  docker run --rm --entrypoint bash lakehouse/spark:4.0.0 -c \
    'ls /opt/spark/jars | grep -E "hadoop-client-api|hadoop-aws|awssdk|delta|unitycatalog"'
  ```

- **Changes to `spark-defaults.conf` appear to have no effect.** It is baked
  into the image, not mounted. Rebuild and recreate:
  `make stack-up` rebuilds, then recreate `app`, `spark-worker-1` and
  `spark-worker-2` so driver and executors agree.

- **A mounted directory reads as empty inside a container, while the host
  shows files and the smoke test stays green.** Incident 2026-08-09: after a
  squash-merge branch dance (`git checkout main && git pull`), directories
  that did not exist on the old branch were deleted and recreated, and the
  running containers kept bind mounts to the dead inodes. `model/` read as
  empty, `load_all()` returned zero specs, and `make stack-smoke` stayed
  green because it does not read specs. Fix:
  `docker compose up -d --force-recreate app spark-worker-1 spark-worker-2`
  after any branch operation that deletes and recreates mounted directories.

- **Credentials changed in `docker/.env` but the metastore still fails S3
  auth while reporting healthy.** Its healthcheck is TCP-only. The metastore
  reads `docker/hive/core-site.xml`, which is generated from the `.template`
  by `make stack-up`; re-run it after a credential change and recreate
  `hive-metastore`. Never edit the generated file.

- **A script copied with `docker compose cp` disappears.** Recreating a
  container resets its filesystem. Put scripts in `scripts/`, which is mounted
  into the driver at `/opt/lakehouse/scripts`.

## Verifying the pipeline

The integrity evidence lives in four scripts, run through the driver:

```bash
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_bronze.py
```

Same invocation for `verify_silver.py`, `verify_scd2.py` (SCD2 integrity:
overlaps, gaps, inverted ranges, current-per-key), `verify_gold.py` (grain,
orphan keys, balance continuity, milestone ordering) and `demo_queries.py`
(business questions by name). `make test-spark` runs the transformation unit
tests inside the container, where pyspark lives.

## Last verified

- **Last verified:** 2026-08-10 against `lakehouse/spark:4.0.0`, Hive
  Metastore 4.0.1, Unity Catalog v0.5.0 (pinned), MinIO
  RELEASE.2025-09-07T16-13-09Z, at the commit carrying review-06's fixes.
  Steps 1 to 3 and 6 executed this day (smoke green on the pinned UC image,
  all verify scripts green including the inverted-range check); steps 4, 5
  and 8 last executed in full during the phase-09 demo run and the review-06
  convergence reproduction, against the same images.
