# 0001. Tiered docs scaffold with machine enforcement

- **Status:** Accepted
- **Date:** 2026-08-07

## Context

The docs pipeline in this repo (research → ADR → plan → audit, plus runbooks)
was copied from another project and is intended to seed every future repo. An
adversarial review of it surfaced three failures that only appear over time,
which is exactly when a template is hardest to change:

1. Every rule lived in prose. "Never push to `main`" and "squash-merge only"
   are GitHub settings, not conventions, and a rule an agent can forget is not
   a rule.
2. Each of the five surfaces carried a hand-maintained index table. A
   hand-maintained cache of the filesystem drifts, and the repo's own build
   brief argues the opposite position for its diagrams.
3. The scaffold had no opt-out. Applied uniformly to a throwaway script it
   generates ceremony, and a process that feels like ceremony gets abandoned
   wholesale rather than trimmed.

There is also a trigger problem: "every significant decision gets an ADR" has
no failure condition, and a generative agent asked to judge significance will
over-produce. A corpus of forty ADRs where eight matter is worse than eight.

## Options considered

**A. Leave it as convention.** Prose rules, hand-maintained tables, all five
surfaces mandatory.
- Pros: zero code, nothing to maintain, works fine for one attentive person.
- Cons: every failure above lands eventually and silently; the drift is only
  visible to someone who reads both the index and the directory.

**B. Delete the index tables, keep the rest as convention.** `ls docs/adr/` is
a free index.
- Pros: laziest possible fix, removes the drift class entirely.
- Cons: loses the one thing the filesystem cannot show, which is ADR status.
  A reader landing on a superseded decision has no way to know without opening
  every file.

**C. Generate the indexes, move enforceable rules into config, tier the
surfaces.** A ~200 line stdlib script, a Makefile, a CI job, a PR template,
branch protection.
- Pros: drift becomes a failing build; the honour-system rules that a machine
  can hold are held by a machine; the scaffold scales down to a small repo.
- Cons: the template now carries code, which needs its own test and can itself
  rot. Python is now a template dependency even for a non-Python project.

## Decision

**We will adopt option C: generated indexes, machine-enforced discipline, and
explicit tiers, for this repo and every repo cookie-cuttered from it.** The
scaffold's value is that it survives contact with a busy month, and only the
enforced parts survive.

Scope and specifics:

- `scripts/docs_index.py` generates the index tables and checks the rules a
  reviewer would otherwise hold in their head: index freshness, dangling
  supersede links, duplicate ADR numbers, and in-progress plans that have gone
  silent for 60 days. `make check` runs it, CI runs `make check`.
- The ADR trigger becomes cost of reversal, over one day, rather than
  significance.
- Tier 0 is `docs/adr/` plus `docs/runbooks/`; tier 1 adds `docs/plans/`; tier
  2 adds `docs/audits/` and `docs/research/`. The generator skips a surface
  whose README is absent, so deleting a directory is the whole opt-out.
- Audit findings carry severity and priority only. A third axis gets filled in
  dishonestly.

## Consequences

Index drift and dangling supersede links become build failures rather than
things a reader discovers. "Never push to `main`" is enforced by branch
protection, so it stops consuming review attention.

The template now owns code. `scripts/docs_index.py` has one test and will need
maintenance; a non-Python project inheriting the template inherits a Python
dependency it may not otherwise want, and would need to port the script or
drop the checks. That cost is accepted because the checks are the part that
makes the rest real.

The staleness rule will occasionally fail CI on a PR unrelated to the stale
plan. That is the intended pressure, but it is friction on someone who did not
cause it.

**Revisit when:** the generator needs a second non-trivial feature (an argument
that it wants to be a real tool rather than a script), or when a project
inheriting this template is not Python and has to port it. Either is the
signal that the enforcement layer has outgrown a 200 line script.

## Related

- `docs/runbooks/start-a-new-project.md`: the cookie-cutter procedure this
  decision produces.
- `docs/initial-prompt.md`: the build brief whose "docs that cannot drift from
  code" argument is applied here to the docs pipeline itself.
