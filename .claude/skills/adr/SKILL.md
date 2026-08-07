---
name: adr
description: Create an Architecture Decision Record in docs/adr/ following the repo's ADR conventions (Nygard format + options considered, NNNN-slug.md numbering, immutable-once-accepted). Use whenever a significant decision is being made or has just been made — a fork between technologies/patterns/schemas, a research finding being promoted to a commitment, a deliberate rejection of an obvious option, an accepted trade-off, or a reversal of a prior ADR. Also use when the user says "write an ADR", "record this decision", "capture this choice", or when a discussion ends with a clear verdict between real alternatives.
---

# adr — record an architecture decision

Create one ADR in `docs/adr/`, following `docs/adr/README.md` conventions and
`docs/adr/template.md` structure exactly.

## Workflow

1. **Confirm it deserves an ADR.** The test is cost of reversal: would
   unwinding this six months from now cost more than a day? If no, say so and
   stop — don't generate ceremony.
2. **Determine the number.** `ls docs/adr/` → next 4-digit sequence (never reuse,
   never renumber). Slug: short, lowercase, hyphenated, states the decision
   (`0003-postgres-for-the-metadata-store.md`, not `0003-database.md`).
3. **Draft from the template** (`docs/adr/template.md`). Rules:
   - **Context**: forces and constraints only, no solutions. A stranger to the
     repo must understand the tension.
   - **Options considered**: 2–4 real options, one line + pros/cons each. Include
     the option that was rejected despite being popular/obvious, if any.
   - **Decision**: one bold sentence — "We will X, because Y." Scope it
     ("for the knowledge plane only", "until 10k users").
   - **Consequences**: what gets easier, harder, committed, risked — and a
     **specific revisit trigger** (metric, date, or event; never "if needed").
   - Length: one to two pages. Cite research docs (`docs/research/**`) and PRs
     in **Related** instead of repeating their analysis.
4. **Status:**
   - Decision already made by the user in conversation → `Accepted`.
   - Proposing for review → `Proposed`; the user flips it to `Accepted` (or it
     gets accepted in PR review).
   - Superseding: new ADR references the old in **Related**; edit the old ADR's
     status line to `Superseded by [NNNN](NNNN-slug.md)` — that line is the only
     permitted edit to an accepted ADR.
5. **Regenerate the index**: `make docs`. Never hand-edit the table between the
   `<!-- index:start -->` markers; it is generated from each ADR's `# ` heading
   and `- **Status:**` line. Run `make check` before handing back.
6. **Report**: file path + one-line decision statement. If the ADR was created
   mid-task, continue the task; land the ADR in the same branch/PR as the work
   it governs.

## Hard rules

- One decision per ADR. Two decisions → two ADRs, cross-linked.
- Never edit the body of an Accepted ADR. Supersede instead.
- Never renumber or reuse numbers, including for rejected ADRs.
- ADRs record *why*; runbooks record *how*; research docs record *analysis*.
  Don't let the ADR absorb either.
