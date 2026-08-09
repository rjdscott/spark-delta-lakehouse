# Standalone Hive Metastore. Not HiveServer2, not Hive-on-MR: only the
# metastore service, which is the piece Spark, Trino, Flink and DuckDB all
# speak. Hive the query engine is not part of this platform.
ARG HIVE_IMAGE=apache/hive:4.0.1

# The Hive image ships no download tool (curl returns exit 127), so fetch in a
# stage that has one.
FROM alpine:3.20 AS fetch
ARG POSTGRES_JDBC_VERSION=42.7.4
# The metastore creates the warehouse directory itself, so it needs the s3a
# filesystem too. Its Hadoop is 3.3.6, which uses AWS SDK v1, while Spark's
# Hadoop 3.4.1 uses v2. Two different SDK majors in one stack is correct: the
# version matrix is per process, not per platform.
ARG HIVE_HADOOP_VERSION=3.3.6
ARG HIVE_AWS_SDK_VERSION=1.12.367
RUN apk add --no-cache ca-certificates wget \
 && M=https://repo1.maven.org/maven2 \
 && wget -q -O /tmp/postgresql.jar \
    $M/org/postgresql/postgresql/${POSTGRES_JDBC_VERSION}/postgresql-${POSTGRES_JDBC_VERSION}.jar \
 && wget -q -O /tmp/hadoop-aws.jar \
    $M/org/apache/hadoop/hadoop-aws/${HIVE_HADOOP_VERSION}/hadoop-aws-${HIVE_HADOOP_VERSION}.jar \
 && wget -q -O /tmp/aws-sdk-bundle.jar \
    $M/com/amazonaws/aws-java-sdk-bundle/${HIVE_AWS_SDK_VERSION}/aws-java-sdk-bundle-${HIVE_AWS_SDK_VERSION}.jar

FROM ${HIVE_IMAGE}
# The image ships no JDBC driver at all, so a Postgres-backed metastore cannot
# start without this. Derby is the default and is single-process, which is the
# thing we are moving away from.
COPY --from=fetch /tmp/postgresql.jar /opt/hive/lib/postgresql.jar
COPY --from=fetch /tmp/hadoop-aws.jar /opt/hive/lib/hadoop-aws.jar
COPY --from=fetch /tmp/aws-sdk-bundle.jar /opt/hive/lib/aws-java-sdk-bundle.jar
