# One image for the master, the workers and the driver. A standalone cluster
# only works if every node has an identical classpath, and the surest way to
# guarantee that is to ship one image rather than three sets of --jars flags.
#
# Jars are resolved at build time and baked in, so a demo does not depend on
# Maven Central being reachable, and so the first run is not slower than the
# rest. The resolution uses Ivy through spark-submit rather than a hand-picked
# list of URLs, because these packages have transitive dependencies (jackson,
# antlr, the UC client) that are easy to get subtly wrong by hand.

ARG SPARK_IMAGE=apache/spark:4.0.0-scala2.13-java17-python3-ubuntu
FROM ${SPARK_IMAGE}

ARG DELTA_ARTIFACT=delta-spark_4.0_2.13
ARG DELTA_VERSION=4.1.0
ARG UC_CONNECTOR_VERSION=0.4.1
ARG HADOOP_VERSION=3.4.1
ARG AWS_SDK_VERSION=2.24.6
ARG SCALA_VERSION=2.13
ARG SPARK_VERSION=4.0.0

USER root

ENV PACKAGES="io.delta:${DELTA_ARTIFACT}:${DELTA_VERSION},\
io.unitycatalog:unitycatalog-spark_${SCALA_VERSION}:${UC_CONNECTOR_VERSION},\
org.apache.hadoop:hadoop-aws:${HADOOP_VERSION},\
software.amazon.awssdk:bundle:${AWS_SDK_VERSION}"

# SparkPi is a throwaway: the job is not the point, resolving the packages is.
# SPARK_LOCAL_IP is set because the build container has no resolvable hostname
# and Spark refuses to start without one.
RUN SPARK_LOCAL_IP=127.0.0.1 /opt/spark/bin/spark-submit \
      --master 'local[1]' \
      --packages "${PACKAGES}" \
      --conf spark.ui.enabled=false \
      --class org.apache.spark.examples.SparkPi \
      "/opt/spark/examples/jars/spark-examples_${SCALA_VERSION}-${SPARK_VERSION}.jar" 1 \
    > /tmp/resolve.log 2>&1 \
 || (cat /tmp/resolve.log && exit 1)

# Ivy's cache directory name tracks the Ivy version, which tracks the Spark
# version, so find it rather than hardcoding ~/.ivy2.
RUN set -eux; \
    IVY_JARS="$(find /root -type d -path '*/jars' -name jars | head -1)"; \
    test -n "${IVY_JARS}"; \
    cp "${IVY_JARS}"/*.jar /opt/spark/jars/; \
    rm -rf /root/.ivy* /root/.m2; \
    ls /opt/spark/jars/ | grep -cE 'delta|unitycatalog|hadoop-aws|bundle'

COPY docker/spark/spark-defaults.conf /opt/spark/conf/spark-defaults.conf

# The driver container runs our code; the master and workers only need the
# classpath. Installing here keeps one image rather than two.
COPY pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir pyyaml

# Spark 4 materialises an artifacts/ directory relative to the working
# directory on session start. The image runs as the unprivileged spark user, so
# a root-owned WORKDIR fails with AccessDeniedException before any job runs.
RUN mkdir -p /opt/lakehouse/artifacts /opt/lakehouse/warehouse \
 && chown -R spark:spark /opt/lakehouse

ENV PYTHONPATH=/opt/lakehouse/src
WORKDIR /opt/lakehouse
USER spark
