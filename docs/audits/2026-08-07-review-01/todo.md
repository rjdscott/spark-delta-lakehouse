# Punchlist: review-01

Severity `<C|H|M|L>-NN`, priority P0 ship-blocker / P1 before the template is
reused / P2 soon / P3 nice.

- [x] **H-01** P0: ignore future dates when computing plan last-activity, so a
  target date cannot mask an abandoned plan. [`01-scaffold.md#h-01`](01-scaffold.md#h-01)
- [x] **H-02** P1: resolved by decision, not by fix. `main` stays unprotected
  deliberately; recorded in [ADR 0002](../../adr/0002-branch-rules-stay-honour-code.md)
  and stated plainly in `CLAUDE.md`. Needs the repo owner to run step 7 of
  `docs/runbooks/start-a-new-project.md`. [`#h-02`](01-scaffold.md#h-02)
- [ ] **M-03** P2: staleness rule for runbooks, 180 days against
  `Last verified`. [`#m-03`](01-scaffold.md#m-03)
- [x] **M-04** P0: test the drift detection itself; fix the two defects it
  surfaced. [`#m-04`](01-scaffold.md#m-04)
- [x] **M-05** P3: drop the unread `Date` field from audit conventions.
  [`#m-05`](01-scaffold.md#m-05)
- [x] **L-06** P3: state plainly that docs-in-the-same-PR is honour code.
  [`#l-06`](01-scaffold.md#l-06)
- [ ] **L-07** P3: no action; recorded so it is not rediscovered as a
  mystery. [`#l-07`](01-scaffold.md#l-07)

## Deliberately not doing

- **CI rule forcing a plan update on any `src/` change.** Fires on unrelated
  PRs and trains people to bypass the gate.
- **Dependabot and dependency scanning.** Worth adding when the repo has real
  dependencies; `uv.lock` plus two dev tools does not earn it yet.
