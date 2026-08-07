# 0002. Branch rules stay honour code

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

`CLAUDE.md` opens with "Never push to `main`" and "Squash-merge only". ADR 0001
argued that rules a machine can hold should be held by a machine, and moved
several rules from prose into `make check` and CI on that basis. Branch
protection is the obvious machine for these two.

Two audits left this open. review-01 found `CLAUDE.md` claiming protection was
in force when it was not. review-02 named it the single item blocking template
status, on the grounds that every repo created from this template inherits the
answer, and an inherited omission is worse than an inherited decision.

The apparent constraint turned out to be false. The repo is public, and branch
protection is free for public repositories on any plan. The `422` that looked
like a billing limit was this runbook sending `-f 'enforce_admins=true'`, which
the API rejects because `-f` makes every value a string. So the choice is real,
not forced.

## Options considered

**A. Enable branch protection.** Require a PR and a green `check` job for every
change to `main`, applied to admins too.
- Pros: the top two rules stop being honour code; the enforcement matches what
  the documentation already claims; children inherit a working gate.
- Cons: applies to the owner working alone on their own repo, including at the
  moments protection is least welcome, such as a one-character fix to unbreak
  CI. `enforce_admins` means the escape hatch is a settings change, not a flag.

**B. Leave `main` unprotected, and say so.** The rules stay conventions, stated
as conventions.
- Pros: no friction for a solo owner; nothing to unpick when a repo made from
  this template has different needs; the local checks that catch real damage
  (`make check`) run regardless.
- Cons: the strongest rule in the scaffold is unenforced, and a rule that is
  only written down is one an agent or a hurried human can skip. The gap has to
  be stated honestly everywhere it matters, or it becomes review-01 H-02 again.

**C. A `pre-push` hook installed by `make setup`.** Local speed bump, bypassable
with `--no-verify`.
- Pros: catches the accident without blocking the deliberate act.
- Cons: not enforcement, and it adds a file and a `core.hooksPath` side effect
  to `make setup` that a child repo inherits silently. Rejected as ceremony
  dressed as a control; the decision below can be revisited into it cheaply if
  the accident actually happens.

## Decision

**We will leave `main` unprotected and treat the branch rules as honour code,
for this repo and as the template's default.** The owner works alone, the
checks that prevent real damage run locally and in CI regardless, and the cost
of the gate falls entirely on the one person it would be protecting.

This is a decision, not an omission. `CLAUDE.md` states plainly that the branch
rules are unenforced, and `docs/runbooks/start-a-new-project.md` step 7 carries
a working command so a child repo can turn protection on without rediscovering
the API.

## Consequences

A push straight to `main` will succeed. Nothing will catch it, and the history
will show it. Anyone reading `CLAUDE.md` now learns that from the document
rather than from an incident.

Child repos inherit an unprotected `main` and an examined reason for it. A
project with more than one contributor should reverse this on day one; step 7
of the runbook is the whole procedure and takes one command.

The scaffold's claim to be machine-enforced is now narrower and accurate: it
covers docs integrity, lint, and tests, and it does not cover branch
discipline.

**Revisit when:** a second person commits to any repo made from this template,
or the first accidental push to `main` happens. Either event makes option A or
C cheap to justify, and both are one command away.

## Related

- [ADR 0001](0001-tiered-docs-scaffold-with-machine-enforcement.md), which
  established the "machines hold what machines can hold" principle this
  decision deliberately declines to apply here.
- [review-01 H-02](../audits/2026-08-07-review-01/01-scaffold.md), which found
  the false claim, and
  [review-02](../audits/2026-08-07-review-02/00-executive-summary.md), which
  made resolving it a precondition for template status.
- `docs/runbooks/start-a-new-project.md` step 7, the reversal procedure.
