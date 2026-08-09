# Findings: what is not tested, and what is no longer true

Audited at `51e28b1`, against a fresh clone.

<a id="h-01"></a>
## H-01: the transformation code has no automated tests

**Evidence.** 44 tests live in three files: `test_generate.py`,
`test_spec.py`, `test_docs_index.py`. Searching the suite for imports of the
pipeline modules returns `lakehouse.spec` and nothing else.

| Module | Tests |
|--------|-------|
| `generate.py` | yes |
| `spec.py`, `ddl.py` | yes |
| `catalog.py` | **none** |
| `bronze.py` | **none** |
| `silver.py` | **none** |
| `scd2.py` | **none** |
| `gold.py` | **none** |

Everything that makes this a lakehouse rather than a CSV generator is in the
untested half. The SCD2 timeline rebuild, which took four failures and a
convergence proof to get right, has no test. The as-of join that resolves
12,967 facts to non-current versions has no test.

**Impact.** `make check` passes on a change that breaks any of it. The four
`verify_*.py` scripts do check these properties, thoroughly, but they are run
by hand and nothing requires them. The repo therefore has strong verification
and no regression protection, which is the combination that decays quietly:
the checks stay correct and stop being run.

**Fix.** The transformations are pure DataFrame functions and can be tested
against a local Spark session with a handful of rows, without MinIO, without a
metastore, without the cluster. `rebuild_timeline`, `deduplicate`, `coerce`,
`surrogate` and the as-of join are all reachable that way. That is a fast test
suite, not an integration harness.

<a id="h-02"></a>
## H-02: the README says there is no pipeline

**Evidence.** `README.md`, line 7:

```
Status: scaffold only. No pipeline code yet.
```

There are nine phases of pipeline, three fact grains and 288,310 rows in a
snapshot table.

**Impact.** It is the first thing anyone reads, and the brief's standard is a
repo that is read as much as run. A reader who believes this line stops there.

<a id="h-03"></a>
## H-03: the runbook describes a stack that no longer exists

`docs/runbooks/run-the-lakehouse-stack.md` was last accurate at phase 02.

**Evidence.**

- Step 2's expected output lists `catalog-db`, `minio`, `unitycatalog`,
  `spark-master`, two workers and `app`. It omits `hive-db` and
  `hive-metastore`, two of the eight services, and the metastore is the catalog
  the pipeline actually runs on.
- Step 3 instructs the reader to create catalogs and schemas in Unity Catalog
  through its REST API. Correct at the time, and now describing a system that
  is deliberately not on the read path per ADR 0005.
- There is no procedure for running the pipeline. `make generate`, `make seed`,
  `make demo` and the four verification scripts appear nowhere.

**Impact.** `CLAUDE.md` states that a PR invalidating a runbook's steps updates
it in the same PR. That rule was broken by phases 02 through 09, by me, every
time. A stranger following this runbook reaches a smoke test and stops, having
never run the thing the repo is for.

<a id="m-04"></a>
## M-04: the version matrix was never in the repo

`docker/.env` was matched by the standard `.env` gitignore rule and went
untracked for the entire build, while ADR 0003 called it load-bearing
documentation. A fresh clone could not build the Spark image.

**Evidence.** CI on the merge PR: `Makefile:8: docker/.env: No such file or
directory`. Nothing before that ran from a clean checkout.

Fixed before merge. Recorded because the class matters more than the instance:
every local run used a working tree that already had the file, so the
convincing evidence of correctness was produced in the one environment where
the bug was invisible. CI now covers it by construction, since it does
`make setup` on a fresh checkout.

<a id="m-05"></a>
## M-05: a phase document's expected output is stale

`phase-08-gold-star-schema.md` records `null keys=   294` as expected. Phase 09
took that to zero with the unknown-party member. A reader running the
verification would see a better number than the document promises and have to
work out which is right.

<a id="m-06"></a>
## M-06: five make targets are undocumented

`help`, `lint`, `test`, `stack-logs` and `stack-shell` appear in no document.
`make help` mitigates this for anyone who thinks to run it.

<a id="l-07"></a>
## L-07: the verification scripts are not referenced anywhere

`verify_bronze.py`, `verify_silver.py`, `verify_scd2.py`, `verify_gold.py` and
`demo_queries.py` are the strongest evidence in the repo that the modelling is
correct, and no runbook or README mentions them. They are discoverable only by
listing `scripts/`.
