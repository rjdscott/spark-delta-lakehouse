# CLAUDE.md — spark-delta-lakehouse

## Branch + PR discipline

- **Never push to `main`.** Always branch + PR + squash-merge.
- **Branch naming:** `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`. Slug is short, hyphen-separated, lowercase. Example: `feat/silver-scd2-party`, `fix/asof-join-boundary`.
- **One PR per logical change.** Don't bundle unrelated fixes — they're hard to review and harder to revert.
- **PR title:** `<type>(<scope>): <imperative summary>` (`fix(gold): resolve fact_transaction to the dimension version current at txn_ts`).
- **Squash-merge only.** History stays linear.

## Documentation pipeline (research → ADR → plan → audit, + runbooks)

Four doc surfaces, four skills, one flow:
`docs/research/` (analysis) → `docs/adr/` (decisions) → `docs/plans/`
(execution) → `docs/audits/` (verification). Dated-directory convention
everywhere: `<YYYY-MM-DD>-<slug>/`. Alongside the flow: `docs/runbooks/`
(operations) — ADRs record *why*, runbooks record *how*.

**Docs update as-you-go, in the same PR as the change** — plan status +
progress logs, ADRs at forks, runbook bumps when steps change. The process
itself is teaching material; incidents and recoveries get written down, not
buried.

### Runbooks — `docs/runbooks/`, `/runbook` skill

- Operational how-tos: one task per file, exact copy-pasteable commands,
  **Failure modes** fed by real incidents (dated), **Last verified** stamp.
- Conventions + index in `docs/runbooks/README.md`. A PR that invalidates a
  runbook's steps updates it in the same PR.

### ADRs — `docs/adr/`, `/adr` skill

- **Every significant decision gets an ADR** (`NNNN-slug.md`) — any fork between
  technologies/patterns/schemas, any point demanding deeper research before
  committing, any deliberate rejection of an obvious option, any accepted
  trade-off.
- Nygard format + options considered (`docs/adr/template.md`); conventions in
  `docs/adr/README.md`. Accepted ADRs are immutable — supersede, never edit.
- ADRs land in the same PR as the work they govern.

### Plans — `docs/plans/`, `/plan` skill

- Multi-phase work gets a plan: `docs/plans/<date>-<slug>/` with a status-table
  README + `phase-NN-slug.md` files. Conventions in `docs/plans/README.md`.
- **Resumable by a stranger** is the bar. Status table, checkboxes, and progress
  logs update as-you-go, not at phase end.
- Gates per phase: `make check` green, verification commands run, ADR captured
  at any mid-plan fork.

### Audits — `docs/audits/`, `/audit` skill

- Point-in-time audits of a surface (code, security, UX, data):
  `docs/audits/<date>-<slug>/` with `00-executive-summary.md`, `NN-topic.md`
  findings, and a `todo.md` punchlist. Conventions in `docs/audits/README.md`.
- Findings carry evidence or get dropped; severity codes `C/H/M/L-NN`; audits
  are snapshots — never silently edited after publication.
- Research analysis stays in `docs/research/` (dated workspaces); ADRs, plans,
  and audits cite it, never restate it.

## Linked docs

- `docs/adr/README.md` — ADR conventions + index of recorded decisions.
- `docs/plans/README.md` — plan conventions + index of phase plans (resumable).
- `docs/audits/README.md` — audit conventions + index of completed audits.
- `docs/runbooks/README.md` — runbook conventions + index of operational how-tos.
- `docs/research/README.md` — research conventions + dated analysis workspaces.
- `docs/initial-prompt.md` — the build brief this repo answers (scope, phasing,
  acceptance criteria). Read it before planning work.
