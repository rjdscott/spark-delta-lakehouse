# The coherence fix is half delivered, and the rule with no test is the one that broke

- **Lens:** correctness of the regenerated data, follow-up on review-03
- **Commit:** 0b144af
- **Method:** inline adversarial probes against the regenerated extracts, checking every coherence claim rather than the ones with tests

## Verdict

Eight of review-03's eleven findings are genuinely closed and the suite is
green at 36 tests. The new coherence rules mostly hold: sign convention is
exact across all three batches, merchant categories no longer mix across
products, geography agrees with itself.

Two of the five coherence claims do not hold, and the pattern connecting them
is worth more than either finding. **The two rules that broke are the two with
the weakest tests.** The opening-balance rule has no test at all, its entry in
`data/DEFECTS.md` points at `fact_daily_balance`, which does not exist yet.
The closed-account rule has a test that checks one batch out of three and
passed while 87 violations sat in batch 1.

This is the same defect class review-03 raised as H-01, committed again in the
fix for review-03. A claim asserted in documentation and not enforced by a
test is not a property of the system; it is an intention.

## Scope

- In: `src/lakehouse/generate.py` and `tests/test_generate.py` as regenerated,
  the coherence claims in `data/DEFECTS.md` and ADR 0006.
- Out: spec, DDL, docs tooling, stack. Unchanged since review-03 apart from
  the packaging and `source` split, both verified working.

## Findings

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 2 |
| Carried open from review-03 | 3 |

Detail in [`01-coherence.md`](01-coherence.md). Punchlist in
[`todo.md`](todo.md).

## Top risks

1. **A test that checks one batch of three.** H-01 passed while 87 rows
   violated the rule it exists to enforce. Partial coverage that reads as full
   coverage is worse than none.
2. **Credit card balances reach minus thirty-two thousand dollars.** H-02.
   This is the number a viewer will look at first, on the product whose
   balance they understand best.
3. **Review-03 H-03 is still open**: nothing compares a physical table to its
   spec, and phase 05 creates the first tables.
