---
name: runbook
description: Create or update an operational runbook in docs/runbooks/ following the repo's conventions (one task per file, exact copy-pasteable commands, failure modes from real incidents, last-verified date). Use when the user says "write a runbook", "document how to X", after resolving an operational incident worth teaching, or when a change invalidates an existing runbook's steps.
---

# runbook: record how, not why

Runbooks live in `docs/runbooks/`; conventions in `docs/runbooks/README.md`.
Division of labor: **ADRs record why, runbooks record how, research records
analysis.** Runbooks double as teaching material. Write for a stranger at a
keyboard.

## Workflow

1. **Confirm it's a runbook.** A repeatable operational task or an incident
   recovery → runbook. A decision between alternatives → `/adr`. Analysis →
   `docs/research/`. One-off trivia → nothing.
2. **One task per file**: `docs/runbooks/<slug>.md`, imperative title.
   Updating an existing runbook beats creating a near-duplicate. Check the
   index first.
3. **Structure** (all four sections, in order):
   - **When to use**: one or two lines.
   - **Steps**: numbered, exact commands, copy-pasteable from a fresh
     clone; show expected output wherever it isn't obvious.
   - **Failure modes**: what actually goes wrong + recovery. Real incidents
     (with date) are the most instructive content in the repo; never omit
     one to look tidy.
   - **Last verified**: date + the commit/context it was tested against.
4. **Verify the commands** before writing them down, where feasible. A
   runbook nobody ran is fiction.
5. **Regenerate the index**: `make docs`. The row comes from the H1 and the
   `- **Last verified:** YYYY-MM-DD against <commit>` line.
6. **Maintenance rule**: any PR that invalidates a runbook's steps updates
   the runbook in the same PR and bumps Last verified.

## Hard rules

- Exact commands, never paraphrases ("run the checks" ✗, `make check` ✓).
- Incidents are appended to Failure modes with their date. The runbook is
  the incident's permanent home; don't bury it in chat history.
- No decision rationale in runbooks. Link the ADR instead.
