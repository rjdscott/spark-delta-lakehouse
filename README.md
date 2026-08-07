# spark-delta-lakehouse

Lakehouse implementation with Spark and Delta Lake: dimensional modelling over
a retail banking domain, built to be read as much as run. See
[`docs/initial-prompt.md`](docs/initial-prompt.md) for the build brief.

Status: scaffold only. No pipeline code yet.

## Quick start

```bash
make setup   # uv sync
make check   # docs-check + lint + test
make help    # every target
```

## How this repo is organised

| Path | Holds |
|------|-------|
| `docs/adr/` | decisions, and what each one costs |
| `docs/plans/` | multi-phase work, resumable by a stranger |
| `docs/audits/` | point-in-time sweeps of a surface |
| `docs/runbooks/` | how to run the operations |
| `docs/research/` | analysis feeding the above |
| `scripts/docs_index.py` | generates the index tables, checks the docs rules |

Conventions live in each directory's `README.md`, and are summarised in
[`CLAUDE.md`](CLAUDE.md).

## Using this repo as a template

The scaffold above the "This project" line in `CLAUDE.md` is generic and meant
to be reused. Procedure, including branch protection and which doc surfaces to
keep at which project size:
[`docs/runbooks/start-a-new-project.md`](docs/runbooks/start-a-new-project.md).
Rationale and trade-offs:
[`ADR 0001`](docs/adr/0001-tiered-docs-scaffold-with-machine-enforcement.md).
