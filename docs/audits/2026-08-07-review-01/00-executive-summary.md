# The scaffold holds, but it overclaimed its own enforcement

- **Lens:** correctness + process
- **Commit:** cc797ac
- **Date:** 2026-08-07
- **Method:** inline, adversarial, every finding reproduced against a working tree

## Verdict

The scaffold does what it says on the two things that matter most: index drift
is a build failure, and the gate runs green from a cold clone. Two findings are
serious and both are the same species of error the scaffold was written to
eliminate, which is a control that is claimed but not actually in force. One is
a real defect in `scripts/docs_index.py` that silently disables the plan
staleness check; the other is `CLAUDE.md` asserting branch protection that does
not exist on this repo.

Nothing here blocks using the repo as a template. Fix H-01 and H-02 before
cookie-cuttering it, because both propagate to every child repo.

## Scope

- In: `scripts/docs_index.py`, `Makefile`, `.github/`, `CLAUDE.md`, the five
  `docs/*/README.md` convention files, `.claude/skills/`.
- Out: `docs/initial-prompt.md` (a brief, not an implementation), the Spark
  pipeline (does not exist yet).

## Findings

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 2 |

Detail in [`01-scaffold.md`](01-scaffold.md). Punchlist in
[`todo.md`](todo.md).

## Top risks

1. **A defect in the enforcement layer is worse than no enforcement layer.**
   H-01 let a plan abandoned in 2020 report itself as active. Green checks that
   are not actually checking are how a scaffold rots while looking healthy.
2. **The template propagates.** Both High findings are baked into anything
   created from this repo, and a child repo will not re-audit them.
3. **The docs-in-the-same-PR rule, the strongest rule in the system, is still
   honour code.** The PR template makes it visible, not enforced. Worth
   stating plainly rather than implying otherwise.
