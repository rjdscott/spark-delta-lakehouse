# Punchlist: review-06

Severity `<C|H|M|L>-NN`, priority P0 data-correctness / P1 before the next
demo / P2 soon / P3 nice.

- [x] **C-01** P0: make deletion survive a rebuild. Deletion state must derive
  from the full set of snapshots seen (bronze holds them all), not from the
  batch being processed, so replay converges in any order. This changes ADR
  0007's mechanism: supersede it, don't patch around it. Then extend the
  convergence test to an order ending in batch 1, which is the order that
  catches it. [`01-findings.md#c-01`](01-findings.md#c-01)
- [x] **M-02** P0: refuse to run `close_vanished` on an empty extract.
  `incoming.isEmpty()` check plus a collapse threshold; ADR 0007 already
  names the guard. [`#m-02`](01-findings.md#m-02)
- [x] **H-03** P1: give the unknown member a flag or exclude it from
  `is_current` counts; `dim_account.is_inferred` is the precedent that keeps
  the spec guardrail satisfied. [`#h-03`](01-findings.md#h-03)
- [x] **H-04** P1: `conformance()` compares all four properties it fetches.
  Three-line fix. [`#h-04`](01-findings.md#h-04)
- [x] **H-05** P1: ADR 0004's status line gains
  `Superseded by [0005](../../adr/0005-hive-metastore-as-the-working-catalog.md)` for the read-path mechanism, the one edit
  an accepted ADR permits. [`#h-05`](01-findings.md#h-05)
- [x] **M-06** P1: exclude `OPENING` from `debit_amount`, `credit_amount`,
  `txn_count` and the first/last-transaction milestones; keep it in
  `movement`. [`#m-06`](01-findings.md#m-06)
- [x] **M-07** P2: pin the UC server image to a digest or release tag.
  [`#m-07`](01-findings.md#m-07)
- [x] **M-08** P2: `make seed` uses the same variables as `demo-reset`.
- [x] **M-09** P2: derive `spark.sql.warehouse.dir` from `LAKEHOUSE_BUCKET`
  at build time, or document the constraint in `.env`.
- [x] **M-10** P2: one credential source; document the Spark env-to-conf
  bridge in `spark-defaults.conf` so the working path is visible; consider a
  deeper healthcheck for the metastore.
- [x] **M-11** P2: prune the dead committer configuration or wire it.
- [x] **M-12** P2: `verify_scd2.py` asserts `effective_to >= effective_from`;
  `close_vanished` stamps end-of-day rather than midnight.
- [ ] **L-13** P3: replace `collect()`+`isin` with a join-based delete guard.
- [ ] **L-14** P3: null-guard the SCD1 sequencing condition.
- [ ] **L-15** P3: record the SCD1-account-owner limitation in the
  fact_transaction spec comment or ADR.
- [ ] **L-16** P3: share the `BEGINNING` sentinel between `scd2.py` and
  `gold.py`.
- [ ] **L-17** P3: healthcheck spark-master; gate `app` on it.
- [x] **L-18** P2: runbook failure mode: containers hold dead-inode mounts
  after a branch switch recreates mounted directories; symptom is an empty
  mount and green smoke tests; fix is `--force-recreate`.
- [x] Append a correction to phase-07's progress log: the 3,1,2 fingerprint
  test was order-lucky; convergence does not hold for orders ending in
  batch 1 until C-01 lands.

## Carried, still open

- review-05 H-01 (no transformation tests), H-02 (README), H-03 (runbook):
  all three P0s from the previous audit remain open and C-01 is the argument
  for H-01 made flesh: a unit test on `rebuild_timeline` + `close_vanished`
  with a three-row deletion case would have caught it years before an agent
  did.

## Method note

Three finder agents (Opus on transformations, Sonnet on infra, Sonnet on ADR
drift), each self-refuting before reporting; coordinator verified every
surviving finding against code or the live stack. Score: one agent Critical
killed by a one-command empirical test; one agent High upgraded to Critical by
live reproduction; two agents independently converged on M-07. The single
most valuable behavior was the agents' willingness to mark their own findings
latent versus live; the single most necessary one was verifying anyway.
