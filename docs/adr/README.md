# Architecture Decision Records

Why the repo is shaped the way it is. ADRs record *why*; runbooks record *how*
(`../runbooks/`); research records *analysis* (`../research/`).

## Conventions

- One file per decision: `NNNN-slug.md`, 4-digit sequence, never reused, never
  renumbered. Slug states the decision (`0003-hash-surrogate-keys.md`, not
  `0003-keys.md`).
- Structure comes from [`template.md`](template.md): Context, Options
  considered, Decision, Consequences, Related.
- **Consequences state what the decision costs**, not only what it buys, and
  name a specific revisit trigger (metric, date, or event).
- One decision per ADR. Two decisions, two ADRs, cross-linked.
- **Accepted ADRs are immutable.** Superseding a decision means a new ADR; the
  only permitted edit to an accepted one is its status line
  (`Superseded by [NNNN](NNNN-slug.md)`).
- Statuses: `Proposed`, `Accepted`, `Rejected`, `Superseded by [NNNN](...)`.
- An ADR lands in the same PR as the work it governs.
- Write it with the `/adr` skill.

## When something deserves an ADR

Any fork between technologies, patterns, or schemas; any point that demands
research before committing; any deliberate rejection of an obvious option; any
accepted trade-off. If there was only one sane option, or the choice is a
cheaply reversible detail, skip it.

## Index

| # | Title | Status |
|---|-------|--------|
| — | none yet | — |
