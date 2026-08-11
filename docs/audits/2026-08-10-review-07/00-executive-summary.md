# The star does not join to its own date dimension, and five other claims a skeptic can falsify in one query

- **Lens:** everything a demonstration audience can check: published claims, model correctness, infrastructure reproducibility, docs integrity
- **Commit:** dfcecd0
- **Date:** 2026-08-10
- **Method:** six Opus finder agents in parallel (claims, SCD2/silver, gold, infra, data/tests, docs), each instructed to self-refute before reporting; Fable coordinator verified every surviving finding against the code or the running stack before publication. 40 raw findings, 4 cross-lens duplicates merged, 0 refuted in verification, 36 published.

## Verdict

The pipeline computes the right numbers and the headline claims reproduce
exactly (14,644 facts on multi-version parties, 12,967 resolved to a
non-current version, committed data byte-identical to the generator at seed
42). What fails this review is the layer a skeptical principal checks next:
the joins the model declares, the sentences the catalog carries, and the
numbers the docs promise. Eight High findings, every one demonstrable in
under a minute from a running stack:

1. `fact_account_lifecycle.opened_date_key` is a declared, ERD-published
   relationship that resolves for **0 of 3,165 rows**, because `dim_date`
   only spans the transaction window ([H-01](01-findings.md#h-01)).
2. 35 accounts are `status = CLOSED` with close dates up to **2030**, so the
   demo's "accounts that closed" query overstates by 12 percent while the
   same accounts hold balances on the final day ([H-02](01-findings.md#h-02)).
3. Three quarters of the "Unknown" merchant spend the demo charts is mortgage
   repayments, which the code's own comment says belong in NOT_APPLICABLE
   ([H-03](01-findings.md#h-03)).
4. Every SCD2 table's catalog comment documents a null `effective_to` that
   never occurs; the documented currency query returns zero rows
   ([H-04](01-findings.md#h-04)).
5. "Converges under any replay order" is still order-lucky one level below
   review-06's C-01: the rebuild reads the lossy stored table, and a no-op
   version dropped today changes the answer when a late arrival lands before
   it. The drop mechanism is live in the shipped data ([H-09](01-findings.md#h-09)).
6. Bronze's `_rescued_data` branch, the one failure the layer was written to
   survive, throws `AnalysisException` every time it is taken
   ([H-16](01-findings.md#h-16)).
7. Nothing in the repo creates the Unity Catalog namespace any more; the
   claim "UC holds the namespace" is true only on the author's machine
   ([H-21](01-findings.md#h-21)).
8. Two plan Verification fences state expected outputs the live stack
   contradicts by 6.6x, including a line review-05 ticked as corrected
   ([H-30](01-findings.md#h-30)).

## Counts

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 8 |
| Medium | 21 |
| Low | 7 |

## What held

The finders also verified and cleared: README's SCD2 headline numbers, seed
determinism across processes, version pins vs running images, sign and
balance coherence per product across all batches, defect presence for
defects 1 to 3 and 5 to 7, the em-dash rule, port assignments, and the
`make help` fix. Review-05 M-06 no longer reproduces; review-04 M-04 has
resolved into correct behavior (106 no-transaction accounts, all closed
before the observation window). Details and the coordinator's verification
notes are at the end of [01-findings.md](01-findings.md#notes).

## Top remediation themes

The punchlist is [todo.md](todo.md). The pattern across the Highs: claims
were written as prose where they should have been written as checks. The
durable fixes are the ones that convert them: drive the orphan-key loop from
`spec.relationships` (closes H-01 and M-07 at once), reconcile gold against
silver instead of against itself (M-05), compare the generator against the
committed extracts (M-18), and create the UC namespace in compose rather
than in a runbook step (H-21).
