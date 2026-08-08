# Run the local lakehouse stack

## When to use

Starting, demonstrating, or debugging the Docker Compose lakehouse: MinIO,
Unity Catalog on Postgres, and a Spark standalone cluster writing Delta tables
to object storage.

## Steps

1. Confirm the Docker CLI is pointed at a running daemon. On a machine with
   Docker Desktop installed but not started, the CLI targets a socket that does
   not exist while the system daemon runs fine:

   ```bash
   docker context ls          # look for the ERROR column
   docker context use default # the system daemon at /var/run/docker.sock
   docker version --format 'server {{.Server.Version}}'
   ```

2. Bring the stack up. First run builds the Spark image, which resolves the jar
   matrix through Ivy and takes a few minutes. Later runs are cached:

   ```bash
   make stack-up
   make stack-ps
   ```

   Expected: `catalog-db`, `minio` and `unitycatalog` healthy, `spark-master`,
   `spark-worker-1`, `spark-worker-2` and `app` up, `minio-init` exited 0.

3. Create the catalog and the medallion schemas in Unity Catalog. These are
   metadata only; the tables themselves are written by Spark:

   ```bash
   UC=http://localhost:8080/api/2.1/unity-catalog
   curl -s -X POST $UC/catalogs -H 'Content-Type: application/json' \
     -d '{"name":"lakehouse","comment":"retail banking lakehouse"}'
   for s in bronze silver gold; do
     curl -s -X POST $UC/schemas -H 'Content-Type: application/json' \
       -d "{\"name\":\"$s\",\"catalog_name\":\"lakehouse\"}"
   done
   curl -s "$UC/schemas?catalog_name=lakehouse"
   ```

4. Prove every seam end to end:

   ```bash
   make stack-smoke
   ```

   Expected output:

   ```
   spark version        : 4.0.0
   master               : spark://spark-master:7077
   rows via catalog     : 1000
   tables in bronze     : ['smoke']
   executors registered : 2
   ```

   `executors registered : 2` is the line that matters. It confirms the job ran
   on the workers rather than in the driver.

5. Confirm the bytes are really in object storage, not on a container's disk:

   ```bash
   docker run --rm --network lakehouse_default --entrypoint sh \
     minio/mc:RELEASE.2024-11-21T17-21-54Z -c \
     "mc alias set l http://minio:9000 lakehouse lakehouse123 >/dev/null && \
      mc ls -r l/lakehouse/bronze/smoke | head"
   ```

   Expected: `_delta_log/00000000000000000000.json` and parquet parts.

6. The visual surfaces, for demonstrating:

   | URL | Shows |
   |-----|-------|
   | http://localhost:9001 | MinIO console. Watch `_delta_log` grow per commit |
   | http://localhost:8090 | Spark master. Workers, cores, running applications |
   | http://localhost:4040 | The job UI, only while a job is running |
   | http://localhost:8080 | Unity Catalog REST API |

7. Shut down. `stack-down` keeps the data, `stack-destroy` does not:

   ```bash
   make stack-down
   make stack-destroy   # also deletes the MinIO and Postgres volumes
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

- **A script copied with `docker compose cp` disappears.** Recreating a
  container resets its filesystem. Put scripts in `scripts/`, which is mounted
  into the driver at `/opt/lakehouse/scripts`.

## Last verified

- **Last verified:** 2026-08-08 against `lakehouse/spark:4.0.0`, Unity Catalog
  0.5.0, MinIO RELEASE.2025-09-07T16-13-09Z. Steps 1 to 6 were all executed;
  `make stack-smoke` returned 1000 rows on 2 executors with the Delta log
  present in MinIO.
