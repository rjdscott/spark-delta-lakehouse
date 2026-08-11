# Findings: six lenses, one coordinator, everything verified

Audited at `dfcecd0`. Finder: which lens surfaced it. Verified: how the
coordinator confirmed it before publication. Live numbers were measured
against the running stack on 2026-08-10.

## The star

<a id="h-01"></a>
### H-01: dim_date does not span the range the facts require; opened_date_key is 100 percent orphan

**Finder:** gold + data lenses independently. **Verified:** live probe.

`build_dim_date` (`gold.py:178-182`) bounds the dimension by the transaction
window only: `min(to_date(txn_ts))` to `max(to_date(posted_ts))`. The spec's
grain sentence says "across the range the facts require", and
`model/gold_fact_account_lifecycle.yml` declares `opened_date_key ->
gold_dim_date`, published in the README ERD as `}o--||`. Measured live:

```
dim_date bounds: 20251216 .. 20260321
lifecycle opened_date_key: non-null=3165 orphan=3165
lifecycle closed_date_key: non-null=287  orphan=141
```

Every account opens 45 to 3,650 days before the first batch, so no open date
can ever fall inside the dimension. `verify_gold.py` runs its orphan loop
over `fact_transaction` only, so `make demo` prints all green. The obvious
query, accounts opened by month written the way the ERD says to write it,
returns zero rows.

**Fix:** widen `build_dim_date` to union in `min(open_date)` and
`max(close_date)` bounded to the observation window from `silver.account`,
and extend the orphan loop to every declared relationship (see M-07 for the
structural version).

<a id="h-02"></a>
### H-02: 35 accounts are CLOSED with close dates up to 2030 and keep transacting through the demo window

**Finder:** gold + data lenses independently. **Verified:** live probe.

`generate.py:192-196` draws `close_date = opened + randint(60, 2000) days`
with no bound at the first batch date, while `status` is already `CLOSED`.
Live: 35 accounts have `status = CLOSED` and `close_date > 2026-03-21` (max
2030-06-28); all 35 hold `fact_daily_balance` rows on the final day; 803
facts sit on them. The demo's "Accounts that closed, and how long they
lasted" counts 287 closed where 252 have actually closed, and `days_open`
includes years that have not happened. This contradicts DEFECTS.md ("No
activity after an account closes") and ADR 0006's coherence contract, and
the two adjacent demo queries contradict each other. The mid-run closure
path does it correctly (`_age_accounts` stamps the batch date); only the
initial draw is unbounded.

**Fix:** clamp the initial draw to on-or-before the first batch date,
regenerate, and add the invariant to `test_generate` and to
`verify_gold.check_lifecycle` (no closed_date_key beyond `max(date_key)`).

<a id="h-03"></a>
### H-03: three quarters of "Unknown" merchant spend is mortgage repayments the code says are NOT_APPLICABLE

**Finder:** claims lens. **Verified:** code read (`gold.py:145-151`,
`generate.py` HOME_LOAN profile) plus reconciliation against
`verify_gold`'s published 2,289 and the demo's 1,792,848 total.

`category_code()` sends every blank-category DEBIT to UNKNOWN. The generator
deliberately emits home-loan repayments as blank-category DEBITs (a home
loan does not buy groceries). So $1.34M of the $1.79M "Unknown" spend in the
demo's first chart is structurally merchant-less repayments, exactly what
the code comment at `gold.py:40-43` says belongs in NOT_APPLICABLE. Defect
6's "about 3 percent" appears to reconcile only because these 431 structural
rows pad the bucket.

**Fix:** classify NOT_APPLICABLE by product as well as by txn_type: a debit
on a product whose profile declares no merchant categories is not a source
gap. Then "Unknown" is the actual defect-6 population.

<a id="h-04"></a>
### H-04: the catalog comment on effective_to documents a null that never occurs

**Finder:** claims lens. **Verified:** `ddl.py:34` read; live tables show
zero nulls, sentinel 9999-12-31 present.

`ddl.py:34` writes "Exclusive end of this version's validity, null if
current" into both SCD2 tables. `scd2.py` deliberately uses the far-future
sentinel instead, with a docstring explaining why. A viewer who trusts the
catalog (the surface the README sells) writes `WHERE effective_to IS NULL`
and gets zero rows.

**Fix:** one line in `ddl.py:34`: "9999-12-31 while current"; rebuild or
`ALTER TABLE ... ALTER COLUMN ... COMMENT` to propagate.

<a id="m-05"></a>
### M-05: verify_gold's balance checks are algebraic identities that cannot fail

**Finder:** gold lens. **Verified:** code read of `gold.py:324-334` vs
`verify_gold.py:112-134`.

`opening_balance` is defined as `closing_balance - movement`, and the
continuity check asserts exactly that identity back; the final-balance check
asserts the running sum equals the sum it is the running sum of. Both read
only `gold.fact_daily_balance`. No script reconciles gold to silver, so any
future change that drops movements (the `>= close_date` boundary at
`gold.py:277` silently discards a transaction dated on close_date) prints
`continuity breaks: 0` regardless. Latent today: silver sum equals gold
movement sum at -13,102,470.48.

**Fix:** replace the tautologies with cross-layer reconciliation:
`sum(movement)` per account equals `sum(silver.transaction.amount)`, and
`sum(txn_count)` equals the non-OPENING silver count.

<a id="m-06"></a>
### M-06: the OPENING measure rule is a 22.4M reconciliation hole the catalog does not explain

**Finder:** gold lens. **Verified:** code read; the finder's live measure
(3,059 rows where movement != debit+credit, sum -22.4M, all on the first
date_key) is consistent with the OPENING exclusion shipped for review-06 M-06.

The exclusion is correct and deliberate; the defect is that it exists only
as a code comment. `movement`'s spec comment reads "net of the day's
transactions", debit_amount and credit_amount have no comment at all, so
`DESCRIBE` shows nothing where an analyst reconciling the measures needs it.

**Fix:** column comments in `model/gold_fact_daily_balance.yml` naming the
OPENING carry rule; optionally assert the identity for all but each
account's first day in verify_gold.

<a id="m-07"></a>
### M-07: relationship declarations generate only diagrams, while two documents say they generate the DDL and the tests

**Finder:** claims lens. **Verified:** grep; `relationships` is consumed by
`model_docs.py` and `spec.py` cross-validation only, and `verify_gold.py`
hardcodes its orphan list for one fact table.

BUS_MATRIX.md (generated wording) says the X "is the same declaration the
DDL, the tests and the ERD are generated from"; README says four things are
generated. Adding a relationship to a spec changes the published diagrams
and adds no check, which is how H-01 shipped.

**Fix:** drive verify_gold's orphan loop from `spec.relationships` across
all facts, which makes the sentence true and closes the H-01 class
permanently; correct the generated wording either way.

<a id="m-08"></a>
### M-08: the query billed as the SCD2 payoff is decided by 8 rows in 75,295

**Finder:** claims lens. **Verified:** logic and defect-3 shape confirmed;
finder's live measurement accepted (one segment-changing party is planted,
367 to 399 parties change address fields).

"Spend by customer segment, as they were at the time" differs from a naive
current-row join by 8 rows, because segment almost never changes; the
attributes that change are address fields no shipped query groups by. The
12,967 count is real (re-verified), but nothing shipped makes it visible.

**Fix:** add one query grouping by a tracked attribute that moves (spend by
state, as-of vs current) so the audience sees the answer change.

<a id="l-09"></a>
### L-09: days_open is computed from the operator's clock

**Finder:** gold lens. **Verified:** `gold.py:395-397` read.

`datediff(coalesce(close_date, current_date()), open_date)`: 2,878 rows
change value every day with no input change, against the module's own
reproducibility argument. **Fix:** anchor to `max(date_key)` from dim_date.

## SCD2 and silver

<a id="h-09"></a>
### H-09: "converges under any replay order" is still order-lucky; the rebuild reads lossy stored state

**Finder:** SCD2 lens. **Verified:** mechanism confirmed at `scd2.py:245`
(`existing` comes from the stored silver table, semi-joined to affected
keys); counterexample traced by the coordinator; drop mechanism confirmed
live.

`rebuild_timeline` permanently discards a version whose tracked fingerprint
equals its predecessor's, and the MERGE deletes it from the table. A
discarded no-op stops being a no-op the moment a later batch delivers an
out-of-order version between it and its predecessor. Counterexample: X at
Jan 15, no-op X at Mar 15, late-arriving Y at Feb 15. In-order replay ends
with current = Y (two versions); any order that delivers the late row before
the no-op ends with current = X (three versions), which is what a
full-history rebuild gives. The in-order run, the one `make demo` performs,
is the wrong one.

The mechanism is live in the shipped data: bronze holds 2,425 distinct
(party_id, updated_at), silver 2,424; the dropped row is P000011's no-op
STUDENT version at 2026-01-01. Benign today because nothing lands between it
and its predecessor, which is the same shape of luck review-06 C-01 exposed:
the phase-07 convergence proof compares orders on data that does not contain
the pattern.

This is the same lesson as ADR 0010 one level down: anything written-once
(here, the pruned timeline) loses to a rebuild. Bronze already holds every
version ever landed.

**Fix:** source `existing` from bronze (all batches, affected keys) instead
of from the stored silver table, so the rebuild always sees full history;
this needs an ADR since it changes the build's read path. Failing that,
retract the universal claim in `scd2.py` and phase-07 and add the
three-batch counterexample to `tests/test_scd2.py` as a known limitation.

<a id="m-10"></a>
### M-10: the empty-snapshot guard passes a one-row extract; a truncated file mass-closes the dimension

**Finder:** SCD2 lens. **Verified:** `scd2.py:178` read: the guard is
`incoming.limit(1).count() == 0`, exactly zero.

ADR 0010 promises "an empty extract is a source failure, not a mass
deletion". A truncated extract with one surviving row derives deletions for
every other current key, exits 0, and `verify_scd2` stays green because the
zero-current count is printed, never asserted.

**Fix:** proportional guard in `apply_deletions` (refuse when the derived
deleted set exceeds a declared fraction of current keys), and make
`verify_scd2` assert the zero-current count against an expected value.

<a id="m-11"></a>
### M-11: apply_deletions reports a count computed without the guard the MERGE applies, and has no test

**Finder:** SCD2 lens. **Verified:** code read: `count` comes from a
semi-join on `is_current` alone; the MERGE adds
`t.effective_from < s.deleted_ts`.

When the review-06 M-12 inverted-range guard refuses rows, the demo still
prints them as "closed as deleted". No test imports `apply_deletions`.

**Fix:** count under the same predicate the MERGE uses, surface refused rows
separately, add a test with a stored version newer than the deletion
evidence.

<a id="m-12"></a>
### M-12: an untracked attribute change is discarded, not applied as type 1, and nothing pins the choice

**Finder:** SCD2 lens. **Verified:** fingerprint filter at `scd2.py:103-108`
covers tracked columns only; the finder's container repro (a corrected
full_name never reaching silver) follows directly.

`tracked: false` reads as type 1 overwrite; what it does is freeze the value
at first sighting, forever if the party never changes a tracked attribute.
No ADR, doc, or test records this. It is also the ordinary way the no-op
versions that make H-09 reachable get created.

**Fix:** decide and pin: either apply untracked attributes as type 1 from
the latest source row, or write the freeze down and assert the surviving
full_name in the existing test.

<a id="m-13"></a>
### M-13: upsert_scd1's docstring credits its guard to defect 3, which never reaches SCD1

**Finder:** SCD2 lens. **Verified:** docstring read; defect 3 is planted on
party, party is SCD2, `silver.main` routes only `history_type == "scd1"`
entities here.

Nothing exercises the sequencing guard: accounts only move forward,
transactions are one batch per txn_id. A regression deleting the condition
passes every test.

**Fix:** either rewrite the docstring as defensive-and-unexercised, or plant
an out-of-sequence account record so the claim becomes true and tested.

<a id="l-14"></a>
### L-14: scd2's dedupe tiebreak orders by tracked columns only, weaker than silver's own answer

**Finder:** SCD2 lens. Two rows tying on key, sequence value and all tracked
columns while differing on an untracked one are broken arbitrarily;
`silver.deduplicate` orders by every column and says why. **Fix:** order by
all attributes, matching the sibling.

<a id="l-15"></a>
### L-15: scd2's module docstring undercounts its defects and never mentions deletion

**Finder:** SCD2 lens. **Verified:** docstring reads "three of the seven";
defects 1, 2, 3 and 7 target the module, and deletion is a third of it since
ADR 0010. Printed by `run_scd2.py --help`. **Fix:** update the count, add a
deletion paragraph pointing at ADR 0010.

## Bronze and data

<a id="h-16"></a>
### H-16: the _rescued_data branch throws AnalysisException every time it is taken

**Finder:** data lens. **Verified:** code read confirms the order of
operations; finder reproduced live (`UNRESOLVED_COLUMN` at `bronze.py:52`).

`bronze.py:50-55` projects the frame down to the declared columns and only
then adds the rescue column, whose expression references the columns just
projected away. A source adding one column aborts the batch with a stack
trace; the docstring says the opposite ("a source that silently adds a field
does not silently lose it"). The branch has never executed because the
generator never emits undeclared columns; `_rescued_data` is decoration in
every bronze row.

**Fix:** attach the rescue column before projecting
(`wide.withColumn(...).select(*declared, RESCUED_COLUMN)`); plant an eighth
defect with an extra source column so the branch is exercised; add a
`read_extract` case to the container test suite.

<a id="m-17"></a>
### M-17: bronze binds CSV columns by position; a dropped column silently shifts every value after it

**Finder:** data lens. **Verified:** `bronze.py:43` reads with an explicit
schema (Spark's `enforceSchema` default binds positionally); finder
reproduced a timestamp landing in `segment` and NULL in `updated_at`.

A NULL `updated_at` is `sequence_by` for both silver builders, so the layer
that exists to preserve evidence would corrupt the sequencing column
silently. The header is already read separately three lines below for the
rescue check; the information to catch it is in hand.

**Fix:** compare the header against `declared` and raise on a missing
column (which also fixes the crash half of H-16's combined case).

<a id="m-18"></a>
### M-18: the determinism test cannot catch process-dependent ordering, and nothing checks data/raw against the generator

**Finder:** data lens. **Verified:** test read: both trees are generated in
one pytest process, so PYTHONHASHSEED-dependent ordering shows the same
order on both sides. Separately `make seed` ships the committed CSVs, which
no check compares to the generator (the finder verified they match today,
sha256, 9 of 9).

**Fix:** replace the twin write with one write compared against the
committed `data/raw` digests. Strictly stronger: cross-process by
construction, and it fails the moment the committed data goes stale, which
is the drift that would silently invalidate every hardcoded number in the
README.

<a id="l-19"></a>
### L-19: DEFECTS.md says forty withheld accounts are referenced by batch 1; 37 are

**Finder:** data lens. Three of the forty have no batch-1 transaction, so
the demo prints 37 inferred members against a document naming forty.
**Fix:** state "the 37 of them that batch 1 references become inferred
members", or pin `len(orphans) == 37` in the defect-4 test.

<a id="l-20"></a>
### L-20: defect 6's published percentages do not match a query

**Finder:** claims lens. Realised rates: 3.13 percent of parties lack a risk
rating (doc says "about 4"); 19.9 percent of raw transaction rows have a
blank merchant category (doc says "about 3", which is the rate only among
rows that would carry one). **Fix:** state realised figures with their
denominators.

## Infrastructure

<a id="h-21"></a>
### H-21: nothing creates the Unity Catalog namespace; the claim is true only on the author's machine

**Finder:** claims lens. **Verified:** grep across Makefile, docker/,
scripts/, src/: no creation call exists. The runbook step that created it
via curl was deleted in `dfcecd0` and replaced by prose asserting the
namespace exists. The live catalog entry carries the deleted step's verbatim
comment string and a 2026-08-08 timestamp.

After `make stack-destroy` (runbook step 8) or on any fresh clone,
`make stack-up` leaves UC empty, and the demo opens http://localhost:8080 to
an empty catalog list right after the README says UC "holds a namespace".

**Fix:** a `uc-init` compose service mirroring `minio-init` that POSTs the
catalog and three schemas, so the claim is true by construction on a cold
stack.

<a id="m-22"></a>
### M-22: runbook step 2 expects "all eight services" and names ten, and `make stack-ps` can never show minio-init

**Finder:** claims + infra + docs lenses independently. **Verified:**
compose defines 10 services; the sentence enumerates all of them;
`stack-ps` is bare `docker compose ps` (Makefile:58), which hides exited
containers, so the documented `minio-init exited 0` is unobservable via the
command given. The count survived a step that was "verified" the day before,
which means the enumeration and the count are not being read together.

**Fix:** drop the count (the enumeration is correct and cannot rot), and
either make `stack-ps` pass `-a` or gate on minio-init with
`depends_on: {minio-init: {condition: service_completed_successfully}}`.

<a id="m-23"></a>
### M-23: bronze.smoke survives every reset while reset.py claims to drop every table

**Finder:** infra lens. **Verified:** `reset.py` iterates specs only; there
is no spec for smoke; `demo-reset` deletes the files underneath it. After
the documented sequence the catalog lists four bronze tables where the model
declares three, and selecting the fourth fails on a missing `_delta_log`.

**Fix:** `DROP TABLE IF EXISTS bronze.smoke` in reset.py, or have
smoke_stack.py clean up after itself.

<a id="m-24"></a>
### M-24: HIVE_IMAGE is not passed to the Spark image build, so client and server pins can skew

**Finder:** infra lens. **Verified:** the spark-master build args list has
no HIVE_IMAGE; the Dockerfile defaults to `apache/hive:4.0.1`;
`spark.sql.hive.metastore.version 4.0.1` is a third copy;
`HIVE_IMAGE_TAG` used by compose is undefined in .env.

Editing HIVE_IMAGE in the file that calls itself "every version in one
place" upgrades the server and leaves the client jars behind, reintroducing
the exact `Invalid method name: 'get_table'` failure the runbook documents.

**Fix:** pass HIVE_IMAGE through the spark build, define HIVE_IMAGE_TAG in
.env, note the coupling next to `spark.sql.hive.metastore.version`.

<a id="m-25"></a>
### M-25: .env's credential inventory names a generated file and omits the hand-maintained copy

**Finder:** infra lens. **Verified:** the comment cites
`docker/hive/core-site.xml` (generated from the template, gitignored) and
does not mention `docker/uc/server.properties:44-45`, which holds the
literal secret and whose own comment says "must match docker/.env".

**Fix:** correct the inventory, or template server.properties the same way
core-site.xml already is, removing the last hand-maintained copy.

<a id="m-26"></a>
### M-26: no memory or disk prerequisite is documented for a stack that advertises 12 GB and ships ~16 GB of images

**Finder:** infra lens. **Verified:** README's prerequisite list is
"Docker with the compose plugin, uv, make", complete-looking and silent on
resources; workers are 6g each, executors were already OOM-killed once at
2g. This machine has 62 GB; the stack has never run anywhere tight.

**Fix:** one line in README and the runbook stating the floor and naming the
two knobs to turn down.

<a id="m-27"></a>
### M-27: the Spark image's Python deps are a hand copy of pyproject.toml, and the COPY suggesting otherwise is dead

**Finder:** infra lens. **Verified:** `Dockerfile:64` copies pyproject.toml;
nothing reads it; the RUN installs a hardcoded list. A dependency added to
pyproject passes `make check` and fails only on the cluster mid-demo with
ModuleNotFoundError.

**Fix:** delete the dead COPY or make it load-bearing; if the list stays
transcribed, comment that it must track pyproject.

<a id="m-28"></a>
### M-28: CLAUDE.md asserts branch protection that the GitHub API says does not exist

**Finder:** infra lens. **Verified:** `gh api .../branches/main/protection`
returns 404 "Branch not protected"; CLAUDE.md:42 says "Branch protection
requires it" while line 18 says main is deliberately unprotected per ADR
0002. Self-contradictory within one file, and false where it is specific.

**Fix:** reword to what is true: CI reports on every PR; nothing blocks the
merge (ADR 0002); a second contributor flips protection on per the
start-a-new-project runbook.

<a id="l-29"></a>
### L-29: no .dockerignore; both builds ship the whole repo as context

**Finder:** infra lens. 63 MB walked per `make stack-up` (40 MB of it
.venv) for Dockerfiles that COPY two files. **Fix:** one .dockerignore.

## Documentation

<a id="h-30"></a>
### H-30: plan Verification fences state expected numbers the live stack contradicts, including one ticked as corrected

**Finder:** docs lens. **Verified:** phase-08:41 says
`facts via UNKNOWN category: 15,140`; live output is 2,289 (the review-06
M-06 split changed the number's meaning and the fence was not updated,
although review-05 M-05 is ticked as having corrected this block).
Phase-07:36 says `same-day versions : 3 keys`; live is 2 (the ADR 0008
sentinel moved first versions off their batch dates), and the fence predates
the `inverted ranges` line, so the documented shape no longer matches the
real output either.

The Verification blocks are the repo's contract for a stranger reproducing
the work; two of three integrity scripts now disagree with them.

**Fix:** paste current output into both fences, keep explanatory
parentheticals outside the fence so it stays byte-comparable, and note on
review-05's todo that M-05 was only partially applied.

<a id="m-31"></a>
### M-31: the deliverable contradicts three bolded constraints of the brief the README calls authoritative, and the amendment lives only in a superseded plan

**Finder:** docs lens. **Verified:** initial-prompt lines 106, 108, 114
(three services, "No Spark standalone cluster", pip-and-no-Docker) against
the ten-service cluster stack; the brief's demanded "why no Spark cluster"
ADR does not exist; the only record of the requirement change is the
superseded plan's README.

**Fix:** a dated amendment note at the top of the brief, or a "where this
repo departs from the brief" block in README, linking the superseded plan's
note.

<a id="m-32"></a>
### M-32: the completed plan promised five ADRs and delivered one of the five topics

**Finder:** docs lens. **Verified:** the plan's expectation table names
five decisions; only "which catalog" landed (as 0005). Surrogate key
strategy and SCD-type-per-entity clear the repo's own
cost-more-than-a-day-to-unwind bar and have no ADR; both are also in the
brief's minimum set. No progress log records dropping them.

**Fix:** write the two that clear the bar; append dated
judged-below-the-bar notes for the rest.

<a id="m-33"></a>
### M-33: two of the brief's three required diagrams were never built, and pre-commit was neither built nor declined

**Finder:** docs lens. **Verified:** one mermaid block exists repo-wide (the
generated ERD). The layer-flow and SCD2-timeline diagrams survive only as an
unticked task in the superseded plan; the executed plan's docs phase has no
diagram task. The SCD2 timeline over the worked same-day example is the
artifact that makes the 12,967 claim legible to a non-specialist. Same
handover loss: `docs/initial-prompt.md:128` asks for pre-commit with ruff;
none exists and nothing declines it.

**Fix:** add the two diagrams (illustrative, hand-written mermaid over the
real defect-2 party is fine) or record the drop; state that CI-only lint
enforcement is the deliberate pre-commit answer if it is.

<a id="m-34"></a>
### M-34: CLAUDE.md's project section names a dependency file that does not exist and a phasing the repo abandoned

**Finder:** docs lens. **Verified:** `requirements-dev.txt` is absent from
the tree; dev deps live in pyproject.toml/uv.lock via `make setup`. The
"phase 1 is local filesystem" sentence describes the superseded plan.
CLAUDE.md is the file every agent reads first and the one no generated
check covers.

**Fix:** two lines: point at pyproject/uv.lock, restate the phasing as
built.

<a id="l-35"></a>
### L-35: shipped config and live verify output cite the wrong or superseded ADRs

**Finder:** claims lens. **Verified:** `spark-defaults.conf:45` and
`uc/server.properties:8` attribute the vending finding to ADR 0003 (the
version matrix); the same conf file cites 0004 correctly 20 lines earlier.
`verify_scd2.py:40` prints "(deleted parties, ADR 0007)" on every run; 0007
is superseded by 0010. **Fix:** s/0003/0004/ twice; point the live output at
0010.

<a id="notes"></a>
## Coordinator verification notes

- Zero findings were refuted this round. The finders' mandatory
  self-refutation sections killed the weak candidates before submission;
  three of the six lenses reported claims they had already dropped.
- Cross-lens duplicates merged: the future-closed accounts (gold + data),
  the dim_date orphans (gold + data), and the runbook service count (claims
  + infra + docs, three independent finders).
- One finder number corrected: the SCD2 lens reported bronze/silver distinct
  (party_id, updated_at) as 2,400/2,399 (measured over surviving parties);
  the coordinator's probe over all parties measures 2,425/2,424. The
  one-row delta and the dropped row (P000011's no-op STUDENT version at
  2026-01-01) are identical; H-09's mechanism claim is unaffected.
- The coordinator's live probe re-confirmed, unprompted, the README
  headline: 14,644 facts on multi-version parties, 12,967 non-current.
- Cross-ticks against prior reviews: review-05 M-06 (undocumented make
  targets) no longer reproduces and can be closed. Review-04 M-04 has
  changed character: 106 no-transaction accounts, all of which closed
  before the observation window opens, which is coherent rather than
  accidental; close it with that note.
