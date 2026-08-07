# Start a new project from this template

## When to use

Starting any new repo that should inherit the branch discipline, the docs
pipeline, and the `make check` gate.

## Steps

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
   rm -rf docs/adr/0001-*.md          # the template's own ADR, not yours
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

5. Rename the package in `pyproject.toml` (`[project] name`), and update
   `README.md`.

6. Install tooling and confirm the gate is green from a cold clone:

   ```bash
   make setup
   make check
   ```

   Expected: `docs-check` silent, ruff clean, pytest green.

7. Protect `main`. This is what makes "never push to main" real rather than
   an honour system:

   ```bash
   gh api -X PUT repos/rjdscott/<new-project>/branches/main/protection \
     -H "Accept: application/vnd.github+json" \
     -f 'required_status_checks[strict]=true' \
     -f 'required_status_checks[contexts][]=check' \
     -f 'enforce_admins=true' \
     -f 'required_pull_request_reviews[required_approving_review_count]=0' \
     -f 'restrictions=' \
     -F 'allow_force_pushes=false' \
     -F 'allow_deletions=false'

   gh api -X PATCH repos/rjdscott/<new-project> \
     -F allow_merge_commit=false -F allow_rebase_merge=false -F allow_squash_merge=true
   ```

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
- **Branch protection call returns `422 Invalid request`.** Private repos on a
  free plan cannot set branch protection. Either make the repo public, or
  accept that the rule is honour-system only and say so in `CLAUDE.md`.
- **`required_status_checks[contexts][]=check` blocks every PR forever.** The
  context name must match the CI job name in `.github/workflows/ci.yml`
  (`check`). If you rename the job, update the protection rule in the same PR
  or nothing can merge.

## Last verified

- **Last verified:** 2026-08-07 against fd41c4a. Steps 1, 2 and 7 are written
  from the GitHub API docs and have not been run against a fresh repo yet;
  steps 3 to 6 were run in this repo.
