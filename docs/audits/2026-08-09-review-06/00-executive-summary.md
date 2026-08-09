# The convergence proof was order-lucky, and a supported replay corrupts the dimension

- **Lens:** transformation correctness, infrastructure, ADR-vs-code drift
- **Commit:** 51e28b1
- **Method:** three parallel finder agents (one Opus on transformation logic, two Sonnet on infrastructure and on ADR claims), each instructed to refute its own findings before reporting; every surviving finding then independently verified by the coordinator against the code or reproduced against the running stack before publication. One agent finding was killed in verification; one was reproduced live and upgraded to Critical.

## Verdict

Five previous audits, all single-reviewer, said the modelling was correct and
the gaps were in coverage and documentation. This one found the first genuine
data-corruption defect: **replaying batch 1 after a full run resurrects all 25
deleted parties**, reproduced live, current count 1,975 to 2,000, closures
silently erased. Out-of-order replay is not an exotic operation here; it is a
property the repo advertises, tests, and proves with a fingerprint. The proof
used replay order 3,1,2, the single permutation that ends on the batch that
re-closes the deleted parties. Any order ending in batch 1 diverges.

The verification layer also failed sideways during this review: after the
squash-merge branch dance, the app container's `model/` bind mount pointed at
a dead inode, `load_all()` returned zero specs, and the smoke test stayed
green. Green checks over a half-broken system, for the third time in this
project's history.

On the other side of the ledger: the infrastructure agent reported a Critical
claiming Spark could not authenticate to MinIO at all. Empirical falsification
took one command, and the probe that followed found the real mechanism: Spark
bridges `AWS_ACCESS_KEY_ID` env vars into `fs.s3a.access.key` at session
build, which the agent's (correct) reading of the Hadoop source could not see.
A finding that survives source-reading can still die against a running system,
which is why nothing in this audit was published unverified.

## Scope

- In: `src/lakehouse/` transformation logic, `docker/`, `Makefile`, CI,
  `scripts/`, all nine ADRs checked claim-by-claim against the code.
- Out: README/runbook staleness and test coverage (review-05, open), data
  coherence (review-04, closed).

## Findings

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 3 |
| Medium | 7 |
| Low | 6 |
| Refuted in verification | 1 |

Detail in [`01-findings.md`](01-findings.md). Punchlist in [`todo.md`](todo.md).

## Top risks

1. **C-01.** A documented, advertised operation silently corrupts the party
   dimension, and the existing convergence test cannot catch it because it
   tests the one lucky order.
2. **M-02.** An empty or missing party extract closes the entire dimension:
   every current party marked deleted, exit code 0, all integrity checks
   green. ADR 0007 names the guard; nothing implements it.
3. **H-04.** `conformance()` checks one of the four table properties DDL
   writes, so `business_key`, `history_type` and `sequence_by` can drift
   silently, half-reopening the hole review-03 H-03 was raised to close.
