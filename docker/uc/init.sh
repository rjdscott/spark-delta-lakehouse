#!/bin/sh
# Create the Unity Catalog namespace on a cold stack (review-07 H-21).
#
# This used to be a hand-run curl in the runbook, which meant a fresh clone
# or a stack-destroy left UC empty while the README said it held a
# namespace. The POSTs return 409 on an already-created object, which is
# fine; the GET at the end is the actual gate.
set -u
UC=http://unitycatalog:8080/api/2.1/unity-catalog

curl -s -X POST "$UC/catalogs" -H 'Content-Type: application/json' \
  -d '{"name":"lakehouse","comment":"retail banking lakehouse"}' >/dev/null || true
for s in bronze silver gold; do
  curl -s -X POST "$UC/schemas" -H 'Content-Type: application/json' \
    -d "{\"name\":\"$s\",\"catalog_name\":\"lakehouse\"}" >/dev/null || true
done

curl -sf "$UC/catalogs" | grep -q '"name":"lakehouse"' || {
  echo "unity catalog namespace missing after init" >&2
  exit 1
}
echo "unity catalog namespace ready: lakehouse.bronze/silver/gold"
