# Findings: the scaffold and its enforcement layer

Audited at `cc797ac`. Every finding below was reproduced, not inferred.

<a id="h-01"></a>
## H-01: a future date in a plan permanently disables the staleness check

`scripts/docs_index.py:65` took `max()` over every `YYYY-MM-DD` found anywhere
under a plan directory and treated it as the last sign of life. Plans routinely
name a target, a cutover, or a deadline. Any such date is in the future, wins
the `max()`, and the plan reports itself as freshly touched forever.

**Evidence.** A plan whose only real activity was in 2020, with the sentence
"Target 2099-12-31" in its README:

```
$ python3 -c "import docs_index; print(docs_index.render('plans', Path('/tmp/p')))"
('...| [2020-01-01-x](2020-01-01-x/) | X | In progress | 2099-12-31 |...', [])
```

Zero problems reported. The check exists precisely to catch this plan.

**Impact.** The staleness rule, one of the three things `make docs-check`
enforces, is silently defeated by ordinary planning language. Worse than not
having the check, because the green result is read as a statement about the
plan.

**Fix.** Ignore dates in the future when computing last activity. Applied, with
a regression test (`test_target_date_in_the_future_is_not_activity`).

<a id="h-02"></a>
## H-02: CLAUDE.md claims branch protection that is not enabled

`CLAUDE.md` states "Branch protection enforces the first and last of these",
referring to never pushing to `main` and squash-merge only. It does not.

**Evidence.**

```
$ gh api repos/rjdscott/spark-delta-lakehouse/branches/main/protection
{"message":"Branch not protected","status":"404"}
```

**Impact.** This is the exact failure the scaffold was built to remove: a rule
that lives only in prose while asserting that a machine holds it. A reader, or
an agent, that trusts the sentence will believe a push to `main` is impossible.
It is not.

**Fix.** Either enable protection (`docs/runbooks/start-a-new-project.md`
step 7) or reword the claim. Rewording applied; enabling is the user's call
because it changes repo settings.

<a id="m-03"></a>
## M-03: runbooks carry a `Last verified` stamp that nothing verifies

Plans have a staleness rule. Runbooks, which carry `Last verified` and whose
conventions say to bump it, have none. Runbook rot is the more dangerous of the
two: a plan that has gone quiet wastes attention, a runbook with commands that
no longer work fails during an incident, which is the only time anyone reads it.

**Evidence.** `scripts/docs_index.py` has no runbook rule; `runbook_rows`
returns an empty problem list unconditionally (`scripts/docs_index.py:151`).

**Fix.** Add a staleness rule for runbooks with a longer threshold than plans
(180 days). Not applied; see `todo.md`.

<a id="m-04"></a>
## M-04: `main()` and `splice()` were untested, and were broken for any docs root outside the repo

The index generation had a test. The drift detection, which is the entire
reason the script exists, did not.

**Evidence.** Before this audit, `tests/test_docs_index.py` referenced only
`docs_index.render`. Writing the missing test immediately surfaced two real
defects: `main()` raised `ValueError` from `Path.relative_to` for any docs root
outside the repo, and `render`'s `docs: Path = DOCS` default was bound at import
time, so overriding the module's `DOCS` did nothing.

**Impact.** The untested path is the one whose failure mode is silent. If
`--check` stopped detecting drift, every downstream signal would still be
green.

**Fix.** `test_check_mode_reports_a_stale_index` covers stale, rewrite, and
clean. Both defects fixed. Applied.

<a id="m-05"></a>
## M-05: audit conventions require a `- **Date:**` line that nothing consumes

`docs/audits/README.md` asks for `Lens`, `Commit` and `Date` metadata lines.
`audit_rows` reads only `Lens` and `Commit` (`scripts/docs_index.py:137`), and
the directory name already carries the date.

**Impact.** Small, but it is the specific mechanism by which required fields go
wrong: nothing reads it, so nothing notices when it is stale or absent.

**Fix.** Drop `Date` from the conventions. Applied.

<a id="l-06"></a>
## L-06: the docs-in-the-same-PR rule remains honour code

The PR template surfaces the rule as a checklist, which is a real improvement
over nothing, but a checkbox is self-reported. ADR 0001 and the scaffold commit
message can be read as claiming this rule is now enforced. It is not.

**Fix.** No mechanism proposed. A CI rule ("touching `src/` while a 🟡 plan
exists requires touching that plan") produces false positives on unrelated PRs
and would train people to bypass it. Stating it honestly is the better trade.
Applied as wording.

<a id="l-07"></a>
## L-07: `meta()` scans the whole document, first match wins

`meta()` searches the entire file for `- **Key:** value`
(`scripts/docs_index.py:58`). A future ADR that discusses the ADR format, and
quotes a status line as an example above its own, would index the example.

**Impact.** One wrong row in one table. Not worth constraining the search to a
header block today.

**Fix.** None. Recorded so the next person does not rediscover it as a mystery.
