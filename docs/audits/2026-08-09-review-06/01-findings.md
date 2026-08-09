# Findings: three agents, one coordinator, everything verified

Audited at `51e28b1`. Finder: which agent surfaced it. Verified: how the
coordinator confirmed it before publication.

<a id="c-01"></a>
## C-01: replaying batch 1 resurrects every deleted party

**Finder:** Opus (transformation lens). **Verified:** reproduced live.

`rebuild_timeline` reconstructs a key's history purely from its attribute
rows: `_versions()` (`scd2.py`) selects `spec.attributes` only, discarding the
stored `effective_to` and `is_current`. A closure written by `close_vanished`
is therefore not part of what a rebuild sees. And `close_vanished` runs
*after* the merge, so it cannot re-close a key the merge just reopened unless
the key is absent from the current batch's extract.

Deleted parties are present in batch 1 and absent afterwards. Replay batch 1
after a full run: all 25 become `affected`, their timelines rebuild from
attributes alone, `effective_to` reverts to the far-future sentinel,
`is_current` to true, and `close_vanished(present=batch 1)` sees them present
and closes nothing.

**Reproduction, against the running stack:**

```
before  : CURRENT=1975 CLOSED_RANGES=449
replay  : scripts/run_scd2.py --batch 2026-01-15
after   : CURRENT=2000 CLOSED_RANGES=424
```

**The proof that should have caught it:** phase-07 verifies convergence by
replaying 3,1,2 and comparing fingerprints. That order ends on batch 2, whose
`close_vanished` re-closes the 25. Any order ending in batch 1 diverges. The
fingerprint proof is order-lucky, not a proof.

**Corollary (same root cause, latent):** ADR 0007 promises that a reappearing
party "gets a fresh version with a gap in its timeline". The mechanism cannot
produce a gap: on reappearance with unchanged attributes the closure is
erased entirely; with changed attributes the deletion window is absorbed into
the previous version's range. Untriggerable with seeded data, since deleted
parties never return, but the code contradicts an Accepted ADR.

**Fix direction, not smuggled in here:** deletion state must be derivable
from the full set of snapshots seen, not from the single batch being
processed, so that a rebuild converges regardless of order. Bronze holds every
batch and can answer "when did this key last appear". That changes ADR 0007's
mechanism and needs a superseding decision, not a patch.

<a id="m-02"></a>
## M-02: an empty extract closes the entire dimension

**Finder:** Opus. **Verified:** by code inspection; the path is unconditional.

If a batch's party extract is empty or missing, `incoming` is empty, the
merge is a no-op, and `close_vanished` computes `gone` as every current row.
All 1,975 parties get closed with exit code 0, and `verify_scd2.py` reports
zero overlaps, zero gaps, exactly one current-or-zero per key: all green.

ADR 0007 names this exact risk ("an extract whose row count collapses should
fail before it reaches silver") and nothing implements the guard. `build()`
never checks `incoming.isEmpty()`.

<a id="h-03"></a>
## H-03: the gold unknown-party member inflates the current count

**Finder:** Opus. **Verified:** visible in the demo's own output.

The unknown member is created with `is_current = true` and no distinguishing
flag. `demo.py` prints silver at 1,975 current and gold at 1,976 in adjacent
lines. `dim_account` has `is_inferred` for exactly this situation;
`dim_party` has nothing, so the only exclusion is string-matching
`party_id = 'UNKNOWN'`. ADR 0007's stated benefit, counting current parties
without knowing deletions exist, holds in silver and fails in gold.

<a id="h-04"></a>
## H-04: `conformance()` checks one of four table properties

**Finder:** Sonnet (ADR lens). **Verified:** against `ddl.py` and `catalog.py`.

`ddl.py` writes `lakehouse.grain`, `lakehouse.business_key`,
`lakehouse.history_type` and `lakehouse.sequence_by`. `conformance()` compares
only `lakehouse.grain`. Edit `sequence_by` in a YAML after the table exists
and every loader proceeds without complaint. This is the silent-drift failure
mode review-03 H-03 was raised to close, closed halfway.

<a id="h-05"></a>
## H-05: ADR 0005 supersedes ADR 0004 in prose while 0004 stays Accepted

**Finder:** Sonnet (ADR lens). **Verified:** both files read.

ADR 0005's Related section says it "supersedes in practice for the read path";
ADR 0004's status line still reads `Accepted`, and their Consequences sections
contradict each other outright (0004: metadata dies with the driver container;
0005: the catalog survives a full restart, verified). The repo's own rule says
supersession is recorded in the old ADR's status line, the one edit an
accepted ADR permits. `docs_index.py` validates that a `Superseded by` link
resolves, but cannot see a free-text supersession claim in another document,
so `make check` is green over the violated convention.

<a id="m-06"></a>
## M-06: OPENING rows pollute the activity measures

**Finder:** Opus. **Verified:** against `gold.py` and `generate.py`.

`fact_daily_balance` classifies debit/credit purely by sign, and
`fact_account_lifecycle` takes `min(txn_ts)` over all rows, so the
brought-forward `OPENING` row lands in `debit_amount` or `credit_amount`,
inflates `txn_count`, and makes `first_txn_date_key` the window's first day
for essentially every account, degrading `days_to_first_txn` to a constant.
The running balance is correct, since the carry belongs in the cumulative sum;
it is the activity measures that are wrong. A home loan's first "debit" is its
entire principal.

<a id="m-07"></a>
## M-07: ADR 0003 pins the Unity Catalog server; the stack floats it

**Finder:** both Sonnet agents independently. **Verified:** `docker/.env`.

The matrix says UC server 0.5.0, "the image ships it". `docker/.env` says
`unitycatalog/unitycatalog:latest`, the only floating tag in a file whose
stated philosophy is "pinned, not latest, so the demo is reproducible". Every
UC finding in ADRs 0004 and 0005 was reproduced against whatever 0.5.0 image
was current; a fresh pull can silently change that substrate.

<a id="m-08"></a>
## M-08: `make seed` hardcodes what `make demo-reset` parameterises

**Finder:** Sonnet (infra). **Verified:** `Makefile` read; confirmed
`$(MINIO_MC_IMAGE)` et al. are available and used by the sibling target.
Rotate the password in `.env` and `seed` fails while `demo-reset` works.

<a id="m-09"></a>
## M-09: `spark.sql.warehouse.dir` is a baked-in literal

**Finder:** Sonnet (infra). **Verified:** `spark-defaults.conf` is compiled
into the image with `s3a://lakehouse/warehouse` while the metastore and
Python both derive the bucket from `LAKEHOUSE_BUCKET`. Dormant only because
the values coincide.

<a id="m-10"></a>
## M-10: credentials live in three files and a TCP healthcheck hides the break

**Finder:** Sonnet (infra), sharpening review-03 M-07. **Verified:** the
`core-site.xml` copy is load-bearing for the metastore's S3 access, and its
healthcheck is TCP-only, so a credential rotation in `.env` alone leaves the
metastore reporting healthy while every S3-touching operation fails.

<a id="m-11"></a>
## M-11: the S3A committer configuration is dead and its comment overstates

**Finder:** Sonnet (infra). **Verified:** by reasoning accepted after review:
engaging the staging committer requires a commit protocol class and jar this
repo does not carry, and Delta writes bypass Hadoop output committers through
its own commit protocol regardless. The lines are a no-op wearing a warning
comment. Prune or wire correctly.

<a id="m-12"></a>
## M-12: close_vanished stamps midnight, enabling inverted ranges

**Finder:** Opus. **Verified:** by inspection; latent. A key with an intraday
version on date D that is then absent from a corrective re-extract for D gets
`effective_to = D 00:00 < effective_from = D 11:15`. `verify_scd2.py` checks
overlaps and gaps but never `effective_to >= effective_from`. Untriggerable
with seeded data because the deleted set is disjoint from the intraday
parties, which is itself a reminder that the defect sets being disjoint cuts
both ways.

<a id="l-13"></a>
## L-13 to L-18, briefly

- **L-13** (Opus): `whenNotMatchedBySourceDelete` collects every affected key
  to a 2GB driver. Fine at 2,000 keys, wrong shape for a real dimension.
- **L-14** (Opus, latent): `upsert_scd1`'s `>` guard is null-blind; a row
  landing with null `updated_at` can never be updated again.
- **L-15** (Opus, latent): fact party identity resolves through SCD1
  `dim_account.party_id`; an account changing owners would rewrite history.
  The generator never changes owners, which is why this is latent.
- **L-16** (Sonnet, ADR): the `1900-01-01` sentinel is duplicated as bare
  literals in `scd2.py` and `gold.py` rather than shared.
- **L-17** (Sonnet, infra): nothing gates on `spark-master` readiness; the
  ordering that works today is accidental.
- **L-18** (coordinator): after a branch switch that deletes and recreates
  mounted directories, containers keep dead-inode mounts: `model/` read as
  empty while the smoke test stayed green. Belongs in the runbook's failure
  modes.

<a id="refuted"></a>
## Refuted in verification: "Spark cannot authenticate to MinIO"

The infrastructure agent reported a Critical: `SimpleAWSCredentialsProvider`
reads only `fs.s3a.access.key`/`fs.s3a.secret.key`, which are set nowhere for
Spark; only env vars are set; therefore every S3A call fails. The Hadoop
source-reading was correct. The conclusion was falsified in one command:
`make stack-smoke` is green.

The probe that settled it: stripping `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
from the exec environment produces exactly the predicted
`NoAwsCredentialsException`. So the env vars are the credential path, through
a mechanism outside the Hadoop source: Spark's `SparkHadoopUtil` copies AWS
env vars into the Hadoop configuration at session build. The finding dies;
what survives is a documentation note, because the config file reads as if
credentials were configured nowhere, and the working credential path is an
implicit Spark behavior two layers away. Recorded as part of M-10's fix.

<a id="stale"></a>
## Also confirmed: ADR 0008's "still open" claim is closed

The ADR's Consequences say 294 null keys remain and the fix is deliberately
left out. Phase 09 shipped the fix; nulls are zero. Accepted ADRs are
immutable here, so the correction belongs in the punchlist and the phase
docs, not in the ADR body. Noted so the next reader of ADR 0008 has a
pointer: the state it describes ended the same day it was written.
