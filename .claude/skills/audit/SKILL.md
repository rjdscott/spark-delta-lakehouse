---
name: audit
description: Scaffold and run an audit in docs/audits/ following the repo's audit conventions (dated directory, executive summary, NN-topic finding docs, severity codes, todo.md punchlist, evidence-or-drop). Use when the user asks for an audit, review sweep, security review, data-coverage check, or "how healthy is X" across a whole surface — e.g. "audit the pipelines", "run cyber-02", "audit spec conformance", "adversarial review". Not for reviewing a single diff/PR (use /code-review) — audits cover a surface at a point in time and leave a remediation punchlist.
---

# audit — scaffold and run an audit

Conventions live in `docs/audits/README.md` — read it first.

## Workflow

1. **Scope contract first.** Before any digging, write down: surfaces in scope
   (paths), explicitly out of scope, lens (correctness / security / UX / data
   coverage / all), the commit being audited (`git rev-parse HEAD`), and method
   (inline vs. fan-out agents). Confirm scope with the user if it isn't already
   pinned. Fan-out note: bulk agent sweeps run on Sonnet/Opus, not Fable.
2. **Create** `docs/audits/<today>-<slug>/`. Slug names the audit type and
   sequence, matching precedent: `cyber-02`, `review-02`, `coverage-03`, or a
   descriptive slug for one-offs.
3. **Dig, with evidence.** Every finding must carry: severity code
   (`<C|H|M|L>-NN`, unique within the audit), evidence (file:line, command
   output, reproduction steps), impact, and a concrete fix. **Verify or drop**
   — a finding you can't demonstrate does not ship. Adversarially re-check
   Criticals and Highs before publishing.
4. **Write the docs:**
   - `00-executive-summary.md` — verdict first: one-paragraph judgement,
     scope + commit + date + method, findings count by severity, top risks.
     Readable standalone by someone who opens nothing else.
   - `NN-topic.md` — findings grouped by area, reading order. Cross-reference
     with HTML anchors (`<a id="c-01"></a>`) + relative links.
   - `todo.md` — every finding as a checkbox with severity + priority
     (P0 ship-blocker / P1 before public beta / P2 before paid users /
     P3 nice-to-have) + effort tag. This is the implementation handle.
5. **Register it** in the `docs/audits/README.md` index table.
6. **Close the loop:**
   - A fork worth deciding (e.g. "replace X with Y?") → `/adr`, don't bury the
     decision in a finding.
   - Multi-phase remediation → `/plan new <slug>-remediation`, phases citing
     finding codes.
   - Small remediation → work `todo.md` directly on a branch, PR title citing
     the audit.

## Hard rules

- Audits are snapshots: record the audited commit; never silently edit
  findings after publication. Follow-up state lives in `todo.md` ticks and
  successor audits.
- No praise sections, no padding — findings, evidence, punchlist.
- Severity discipline: Critical = exploitable/data-loss/prod-down now; High =
  user-visible defect or foot-gun; don't inflate.
- Remediation PRs cite finding codes; cross-tick the punchlist against git
  history when auditing again (coverage-01 ← coverage-02 is the pattern).
