# Start a new project from this template

## When to use

Starting any new repo that should inherit the branch discipline, the docs
pipeline, and the `make check` gate.

## Steps

0. Prerequisites: `git`, `gh` (authenticated), and `uv`. Without `uv`,
   `make setup` fails with `make: uv: No such file or directory`:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   gh auth status
   ```

1. Mark this repo as a GitHub template, once (skip if already done):

   ```bash
   gh repo edit rjdscott/spark-delta-lakehouse --template
   ```

2. Create the new repo from it:

   ```bash
   gh repo create rjdscott/<new-project> \
     --template rjdscott/spark-delta-lakehouse \
     --private --clone
   cd <new-project>
   ```

3. Strip what belonged to the old project:

   ```bash
   rm -f docs/initial-prompt.md
   rm -rf docs/adr/0001-*.md            # the template's own ADR, not yours
   rm -rf docs/audits/*-review-0*       # audits OF the template, not of you
   ```

   Then edit `CLAUDE.md`: replace everything under `## This project`, and
   leave everything above it alone.

4. Pick a tier and delete the surfaces you have not earned. Tier 0 is
   `docs/adr/` and `docs/runbooks/` only:

   ```bash
   rm -rf docs/plans docs/audits docs/research     # tier 0
   rm -rf docs/audits docs/research                # tier 1
   ```

   The generator skips any surface whose `README.md` is absent, so nothing
   else needs changing. Adding a surface back later is `git checkout` from
   the template.

5. Rename the package in `pyproject.toml` (`[project] name` and
   `description`), and rewrite `README.md`. Both still describe the template's
   own project.

6. Install tooling and confirm the gate is green from a cold clone:

   ```bash
   make setup
   make check
   ```

   Expected: `docs-check` silent, ruff clean, pytest green. If `docs-check`
   reports dead links, they are references to the docs you deleted in steps 3
   and 4. Fix the references; do not delete the check.

7. Protect `main`. This is what makes "never push to main" real rather than
   an honour system:

   The API wants real booleans and integers, so send JSON rather than `-f`
   key/value pairs, which are always strings:

   ```bash
   gh api -X PUT repos/rjdscott/<new-project>/branches/main/protection --input - <<'JSON'
   {
     "required_status_checks": { "strict": true, "contexts": ["check"] },
     "enforce_admins": true,
     "required_pull_request_reviews": { "required_approving_review_count": 0 },
     "restrictions": null,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   JSON

   gh api -X PATCH repos/rjdscott/<new-project> \
     -F allow_merge_commit=false -F allow_rebase_merge=false -F allow_squash_merge=true
   ```

   `required_approving_review_count: 0` still forces a pull request, it just
   does not require someone else to approve it. That is the right setting for
   a solo repo: the rule you want enforced is "not directly on `main`", not
   "wait for a reviewer who does not exist".

   Verify:

   ```bash
   gh api repos/rjdscott/<new-project>/branches/main/protection --jq '.enforce_admins.enabled'
   # true
   ```

8. First commit on a branch, never on `main`:

   ```bash
   git checkout -b chore/project-setup
   ```

## Failure modes

- **`make check` fails on a fresh clone with "index out of date".** The
  template shipped index tables listing docs you deleted in step 3 or 4. Run
  `make docs` and commit the result. This is the generator working correctly.
  Verified 2026-08-07 by cookie-cuttering to tier 0: the failure and the
  recovery both behave as written.
- **`make check` fails with "dead link to docs/plans/".** Same cause, different
  surface: `CLAUDE.md` and `README.md` still point at a tier you removed. Edit
  the references.
- **Branch protection call returns `422 Invalid request`** with
  `"true" is not a boolean`. The `-f` flag sends every value as a string and
  this endpoint type-checks. Use `--input` with JSON, as above. Incident
  2026-08-08: this runbook shipped with the `-f` form, the 422 was read as a
  billing limit, and the repo went a day without protection on the strength of
  a wrong error message.
- **Branch protection genuinely unavailable.** Private repos on a free plan
  cannot use it; public repos can, on any plan. Check with
  `gh repo view --json visibility` before concluding you are blocked. If you
  really are, say so in `CLAUDE.md` rather than leaving the rule looking
  enforced.
- **`required_status_checks[contexts][]=check` blocks every PR forever.** The
  context name must match the CI job name in `.github/workflows/ci.yml`
  (`check`). If you rename the job, update the protection rule in the same PR
  or nothing can merge.

## Last verified

- **Last verified:** 2026-08-07 against 6ced8b9. Steps 3 to 6 were executed
  end to end against a real clone stripped to tier 0, and both documented
  failure modes reproduced. Step 7's payload was corrected on 2026-08-08 after
  the shipped version returned 422; steps 1 and 2 are still written from the
  GitHub API docs and have not been run against a fresh repo.
