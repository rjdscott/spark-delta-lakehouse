# Phase 08: Generated docs and one-command run

## Goal

The definition of done from the brief: a reviewer clones the repo, runs one
command, and gets a populated lakehouse on local disk. They read the README and
the ADRs and reconstruct why every table is shaped the way it is. Nothing
requires verbal explanation.

The diagrams are generated from the specs rather than drawn, for the same
reason the docs index tables are generated: a diagram maintained by hand is a
diagram that disagrees with the code within a month.

## Tasks

- [ ] `make demo` or equivalent: generate sources, run all three layers over
      three batches, print where the warehouse landed and what is in it.
- [ ] Mermaid ERD generated from spec relationships.
- [ ] `docs/BUS_MATRIX.md` generated from which facts reference which
      dimensions.
- [ ] Layer flow diagram, and an SCD2 timeline diagram for the worked
      same-day-change example from phase 05.
- [ ] Generation wired into `make docs` and checked by `make docs-check`, so a
      spec change that outdates a diagram fails the build.
- [ ] `README.md`: the thesis in under 400 words, without evangelism. What the
      repo demonstrates, how to run each phase, and an honest scope statement
      including what brief phase 3 would add and why it is not built.
- [ ] `RUNBOOK.md` or a `docs/runbooks/` entry: execution order per phase and
      what to inspect after each step to confirm it worked.
- [ ] Spec conformance test: every physical table matches its declared spec.
      This is the test that makes the spec load-bearing rather than
      decorative, and it belongs here because only now do all the tables exist.

## Verification

```bash
make check
rm -rf warehouse && make demo
uv run pytest -q                    # full suite, record wall-clock
make docs && git diff --exit-code   # generated docs are current
```

The real verification is social: hand the README to someone who has not seen
the repo and see whether they can say why party is SCD2 and account is not,
without asking.

## Artifacts

- `README.md` rewritten around the thesis
- `docs/BUS_MATRIX.md`, generated
- ERD, layer flow and SCD2 timeline diagrams, generated
- `docs/runbooks/run-the-lakehouse.md`
- `tests/test_spec_conformance.py`
- a `demo` target in the Makefile

## Progress log

Dated appends only. Newest at the bottom.
