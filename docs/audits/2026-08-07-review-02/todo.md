# Punchlist: review-02

Severity `<C|H|M|L>-NN`, priority P0 ship-blocker / P1 before the template is
reused / P2 soon / P3 nice.

- [x] **H-01** P0: dead-link check, so tier-stripping cannot silently orphan
  references. [`01-template-readiness.md#h-01`](01-template-readiness.md#h-01)
- [x] **M-02** P1: make the runbook followable on a clean machine.
  [`#m-02`](01-template-readiness.md#m-02)

## Carried from review-01

- [ ] **H-02** P1: decide branch protection, then record the decision. Enable
  it with step 7 of `docs/runbooks/start-a-new-project.md`, or state in
  `CLAUDE.md` that the branch rules are deliberately honour code. Blocking for
  template status, because every child inherits the answer.
- [ ] **M-03** P2: staleness rule for runbooks, 180 days against
  `Last verified`. Not blocking.
