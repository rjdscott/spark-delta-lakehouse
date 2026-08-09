# Punchlist: review-05

- [ ] **H-01** P0: unit tests for the transformations against a local Spark
      session. `rebuild_timeline`, `deduplicate`, `coerce`, `surrogate` and the
      as-of join, with a handful of rows and no stack.
      [`01-coverage-and-currency.md#h-01`](01-coverage-and-currency.md#h-01)
- [ ] **H-02** P0: rewrite the README. The brief wants the thesis in under 400
      words, how to run each phase, and an honest scope statement.
      [`#h-02`](01-coverage-and-currency.md#h-02)
- [ ] **H-03** P0: bring the runbook up to the current stack, and add the
      pipeline procedure it has never had.
      [`#h-03`](01-coverage-and-currency.md#h-03)
- [x] **M-04** P0: track the version matrix. Fixed before the merge.
- [ ] **M-05** P2: correct the stale expected output in phase 08.
- [ ] **M-06** P3: document or accept the five bare make targets.
- [ ] **L-07** P2: reference the verification scripts from the runbook.

## Carried, still open

- **review-03 M-07**: MinIO credentials duplicated across `docker/.env`,
  `core-site.xml`, `server.properties` and the runbook. Reduced in scope now
  that `.env` is tracked and documented as the source, but still four copies.
- **review-04 M-04**: 116 accounts with no transactions exist by accident
  rather than on purpose.

## Deliberately not doing

- **Running the stack in CI.** Unchanged from review-02: a Spark cluster, MinIO
  and two Postgres instances per PR is a long build. H-01 is the answer, and it
  needs no containers.
