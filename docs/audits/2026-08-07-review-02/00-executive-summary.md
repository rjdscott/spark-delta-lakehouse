# Ready to lock in, once branch protection is a decision rather than an omission

- **Lens:** template readiness
- **Commit:** 6ced8b9
- **Method:** cookie-cuttered the template into a real clone, stripped it to tier 0 following the runbook literally, and ran the gate

## Verdict

The scaffold survives its own procedure. Cloning the template, following
`docs/runbooks/start-a-new-project.md` steps 3 to 6 against a fresh checkout,
and running `make check` produces a working tier-0 repo, and the one failure
the runbook predicted reproduced exactly as documented.

review-01 audited the scaffold as a thing that exists. This audit asked the
different question: what happens when someone uses it. That surfaced one High
that only appears on first use, which is the worst place for a defect in a
template to hide, because the person hitting it is the person with the least
context.

One finding from review-01 remains open by choice and is now the only thing
between this repo and template status.

## Scope

- In: the cookie-cutter path end to end, `scripts/docs_index.py`, the runbook,
  what a child repo inherits.
- Out: the Spark pipeline, which still does not exist. This audit says nothing
  about whether the repo is a good lakehouse, only whether it is a good
  template.

## Findings

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1, fixed |
| Medium | 1, fixed |
| Carried from review-01 | 2, both open |

Detail in [`01-template-readiness.md`](01-template-readiness.md). Punchlist in
[`todo.md`](todo.md).

## Answer to the question asked

Yes, with one decision outstanding. Enable branch protection on `main`
(review-01 H-02, runbook step 7) or consciously accept that the branch rules
are honour code, and say which in `CLAUDE.md`. Every child repo inherits that
choice, and inheriting an unexamined one is how a template teaches a bad habit
at scale.

The other open item, a staleness rule for runbooks (review-01 M-03), is real
but does not block: it costs a stale runbook eventually, not a broken repo on
day one.
