# The infrastructure is honest; the model and one test are not yet

- **Lens:** code quality, modelling rigor, test rigor
- **Commit:** d79bda4
- **Method:** inline adversarial read of every source file, with each finding reproduced against the generated data or the running toolchain

## Verdict

The stack, the docs discipline and the version rigor hold up. The weaknesses
are concentrated in the two places that matter most for a repo whose thesis is
about modelling: **the bronze specs contradict what bronze is for**, and **the
test that proves the hardest seeded defect passes by accident**.

Neither is a slip in unfamiliar territory. Both are cases where the code says
one thing and the documentation next to it says another, which is the failure
this repo exists to argue against. They are cheap to fix now and expensive
after silver is built on top of them.

Nothing here blocks the demo. Everything here would embarrass the demo if a
reviewer read the code carefully, which is the stated quality bar.

## Scope

- In: `src/lakehouse/`, `model/`, `tests/`, `scripts/`, `docker/`, `Makefile`,
  `pyproject.toml`.
- Out: the docs scaffold, audited twice already in review-01 and review-02.
  Gold and silver pipelines, which do not exist yet.

## Findings

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 5 |
| Low | 3 |

Detail in [`01-code-and-model.md`](01-code-and-model.md). Punchlist in
[`todo.md`](todo.md).

## Top risks

1. **A test that passes for the wrong reason is worse than a missing test.**
   H-01 passes only because of dictionary ordering. It will start failing on a
   seed change, and between now and then it certifies nothing.
2. **Bronze is doing silver's job.** H-02 puts type coercion in the raw layer,
   which is the specific discipline failure the repo's thesis is about. Every
   later phase inherits it.
3. **The spec can silently disagree with the table it generated.** H-03: DDL is
   `CREATE TABLE IF NOT EXISTS` and nothing checks conformance, so editing a
   spec after a table exists changes nothing and warns nobody.
