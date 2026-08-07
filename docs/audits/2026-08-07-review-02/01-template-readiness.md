# Findings: what happens when someone actually uses the template

Audited at `6ced8b9`, by cookie-cuttering it rather than reading it.

<a id="h-01"></a>
## H-01: tier-stripping orphans references, and nothing caught it

Deleting `docs/plans/`, `docs/audits/` and `docs/research/` is not damage, it
is step 4 of the runbook and the entire point of the tiers. But `CLAUDE.md`,
`README.md` and the generated indexes all reference those surfaces, and
`make check` passed anyway.

**Evidence.** Clone, then follow the runbook's own steps 3 and 4:

```
$ rm -f docs/initial-prompt.md docs/adr/0001-*.md
$ rm -rf docs/plans docs/audits docs/research
$ make docs && make check
... all checks passed
```

Green, with `README.md` pointing at two files that no longer exist and
`CLAUDE.md` linking three directories that no longer exist. A link checker run
by hand found six dead references.

**Impact.** The template's first act inside a child repo is to produce broken
documentation, silently, at the exact moment the person has least context to
notice. It is also the same failure class the scaffold was built to kill: a
statement about the repo that nothing verifies.

**Fix.** `dead_links()` in `scripts/docs_index.py`, wired into
`make docs-check`. Fenced code blocks are skipped, because they quote example
output rather than link to it, and template placeholders (`NNNN-slug.md`,
`<option>`) are skipped because they are meant to be filled in, not followed.
Covered by `test_dead_links_are_caught_but_placeholders_are_not`. Applied.

**Second defect found while fixing it.** The check originally ran before the
index rewrite, so `make docs` judged the index on rows it was about to remove
and reported a dead link that no longer existed by the time it exited. Moved
after the write loop. This is worth recording because it is the generic trap
in check-and-fix tools: the check must see the post-fix state.

<a id="m-02"></a>
## M-02: the runbook could not be followed literally on a clean machine

Three gaps, all found by executing it rather than reading it.

**Evidence.**

- `grep -c uv docs/runbooks/start-a-new-project.md` returned `0`, while step 6
  runs `make setup`, which is `uv sync`. On a machine without `uv` the
  instruction fails with `make: uv: No such file or directory` and the runbook
  offers nothing.
- Step 3 removed the template's own ADR but not `docs/audits/2026-08-07-review-01/`.
  A tier-2 child repo inherited an audit of a codebase it is not.
- Step 5 said to rename `[project] name` in `pyproject.toml`. The
  `description` field, also template-specific, went unmentioned.

**Impact.** Individually small. Together they mean the runbook is a summary of
what someone remembered doing, not a procedure. The repo's own conventions say
a runbook nobody ran is fiction.

**Fix.** Added a prerequisites step 0 (`git`, `gh`, `uv`, with the install
command), extended step 3 to remove the template's audits, extended step 5 to
`description`, documented the new dead-link failure mode, and re-stamped
**Last verified** against a run that actually happened. Applied.

<a id="carried"></a>
## Carried from review-01, both still open

- **H-02, branch protection.** `main` is still unprotected. `CLAUDE.md` no
  longer claims otherwise, so this is now an honest gap rather than a false
  statement, but every repo made from this template inherits it. This is a
  decision for the owner, not a defect to fix silently.
- **M-03, runbook staleness.** Runbooks carry `Last verified` and nothing
  checks its age. Unchanged. Now slightly more pressing, because
  `start-a-new-project.md` is the one runbook every child repo will rely on
  and the one most likely to drift as GitHub's API changes.

## What was checked and found sound

Recorded so the next audit does not redo it:

- `make check` green from a cold clone with no `.venv`, matching CI.
- No caches, `.idea`, or virtualenvs tracked in git.
- The runbook's predicted "index out of date" failure reproduces exactly, and
  its prescribed recovery (`make docs`) works.
- The generator correctly skips surfaces whose README is absent, so deleting a
  directory really is the whole opt-out.
