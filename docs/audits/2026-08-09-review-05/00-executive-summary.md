# The pipeline works and nothing automated would notice if it stopped

- **Lens:** test coverage, documentation currency, clone-and-run
- **Commit:** 51e28b1
- **Method:** cloned the repo fresh and ran it, then compared every document that describes the system against the system

## Verdict

The lakehouse is correct today. Four verification scripts say so, and they were
run. The problem is that none of them is automated, and the test suite that
does run covers everything except the part that matters.

`make check` is green with 44 tests. Those tests cover the data generator, the
spec loader and the docs tooling. **The transformation code has none at all:**
the SCD2 timeline rebuild, the as-of join, deduplication, type coercion,
inferred members and surrogate keys are exercised only by scripts a human runs
by hand against a running cluster. Break `rebuild_timeline` and the gate stays
green.

The documentation has drifted in the way the repo's own conventions exist to
prevent. The README's first status line says there is no pipeline. The runbook
describes a stack that has not existed since phase 02.

None of this is a defect in the data. All of it is a defect in the ability to
keep the data correct without me in the room.

## Scope

- In: the merged `main` at 51e28b1, a fresh clone of it, and every document
  that claims something about how to run or verify the system.
- Out: the modelling decisions themselves, audited in review-03 and review-04.

## Findings

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 3 |
| Low | 1 |

Detail in [`01-coverage-and-currency.md`](01-coverage-and-currency.md).
Punchlist in [`todo.md`](todo.md).

## Top risks

1. **The gate does not gate the pipeline.** H-01. Five of nine modules have no
   test. A green `make check` is currently a statement about the generator and
   the docs, and it reads as a statement about the lakehouse.
2. **The first line a reader sees is false.** H-02. "Status: scaffold only. No
   pipeline code yet."
3. **The runbook would mislead someone at a keyboard.** H-03. It omits two of
   the eight services, tells them to configure a catalog that is not on the
   read path, and has no procedure for running the pipeline at all.
