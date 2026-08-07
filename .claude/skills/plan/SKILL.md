---
name: plan
description: Create or execute a phase plan in docs/plans/ following the repo's plan conventions (dated directory, status table, phase files, progress logs, resumable-by-a-stranger). Use "/plan new <slug>" (or when the user asks to plan multi-phase work, "write a plan", "break this into phases") to scaffold a new plan; use "/plan execute <dir>" (or "resume the plan", "continue the plan", "work the next phase") to pick up execution from the status table. Enforces make-check-per-phase, ADR capture at decision forks, and as-you-go status/progress updates.
---

# plan: write and execute phase plans

Conventions live in `docs/plans/README.md`. Read it first. Two modes.

## Mode: new (`/plan new <slug>` or a planning request)

1. **Ground it.** A plan executes decisions already made. Check `docs/adr/` and
   `docs/research/**` for the Decisions it builds on; if a major fork is still
   open, stop and resolve it (via `/adr`) before planning around a guess.
2. **Create** `docs/plans/<today>-<slug>/` with:
   - `README.md`: goal (outcome-phrased), scope + non-goals, **status table**
     (`| NN | Phase | Status | Last update |`, statuses: 🔵 Not started /
     🟡 In progress / 🟢 Completed / ⏸ Deferred), critical files, top risks,
     links to the ADRs/research it implements.
   - `phase-NN-slug.md` per phase, each with: **Goal** (one paragraph),
     **Tasks** (checkboxes), **Verification** (exact commands; `make check`
     minimum), **Artifacts** (files that must exist when done),
     **Progress log** (empty, dated appends only).
3. **Phase sizing:** a phase is one PR-sized, independently verifiable slice
   (roughly ≤ a few days). Order by dependency, then risk, so the riskiest
   assumptions surface earliest. 3 to 8 phases typical; more means the plan is
   probably two plans.
4. **Regenerate the index**: `make docs`. The plan README needs an H1 goal and
   a `- **Status:**` line for the row to render.
5. Confirm the plan with the user before execution begins.

## Mode: execute (`/plan execute <dir>` or a resume request)

1. **Orient.** Read the plan's `README.md` status table + the first
   non-completed phase file + its progress log. Never re-derive context that's
   already written there.
2. **Work the phase:** follow CLAUDE.md discipline (branch, one PR per logical
   change). Tick task checkboxes **as each lands**, append to the progress log
   (`YYYY-MM-DD: what happened, what's blocked`), keep the status table
   current. Never rewrite history; append.
3. **Hard gates before marking a phase 🟢:**
   - `make check` green. Can't run it → say so explicitly in the progress log;
     the phase stays 🟡.
   - Verification commands from the phase file executed, output confirmed.
   - Artifacts exist.
4. **Forks:** any mid-plan decision between real alternatives with lasting
   reach → invoke `/adr` before proceeding; link the ADR from the progress log.
5. **Scope changes** get written in (new phase file or amended goal + status
   table row), never silently absorbed. Renumbering is forbidden; new work
   gets new numbers.
6. **Stop points:** end of each phase, report status against the table. If the
   phase file declares a confirmation gate, wait for the user.

## Hard rules

- A stranger must be able to resume from the README alone. That property is
  the definition of done for every update you make to plan docs.
- Status table, checkboxes, and progress logs update as-you-go, not at the end.
- Progress-log entries are dated (`YYYY-MM-DD`). `make docs-check` fails a 🟡
  plan with nothing newer than 60 days, so a stalled plan must be marked
  ⏸ Deferred or deleted rather than left to look live.
- Plans cite ADRs and research; they never restate or re-litigate them.
