# Phase 01: Foundations and the storage seam

## Goal

A Spark session that writes a Delta table to `./warehouse` and reads it back,
reached through one module that is the only place in the codebase aware of
where storage lives. This phase is deliberately thin and deliberately first:
its real job is to find out on day one whether PySpark and `delta-spark` run on
this machine's JVM, and to fix the package layout that every later phase
assumes. It ends with an ADR justifying that layout, because the brief hands
structure to us and asks for the reasoning in writing.

## Tasks

- [ ] Pin PySpark and `delta-spark` as project dependencies, versions matched
      to each other, in `pyproject.toml`.
- [ ] Confirm the JVM situation. If Spark will not run under OpenJDK 25, record
      the required JDK and how to select it, in the runbook, not in someone's
      head.
- [ ] `src/lakehouse/session.py`: a builder returning a configured
      `SparkSession` with the Delta extensions, reading `STORAGE_ROOT` from the
      environment and defaulting to `./warehouse`.
- [ ] `src/lakehouse/paths.py` or equivalent: table path resolution from the
      storage root. Nothing outside these two modules may construct a path or
      know the scheme.
- [ ] `warehouse/` gitignored.
- [ ] `make run` or equivalent smoke target, plus a test that round-trips a
      trivial Delta table through the session builder.
- [ ] ADR: repo structure and the storage seam. Options considered should
      include the flat-module layout and the layer-per-package layout, and the
      consequence section should state what phase 2 will cost if the seam is
      wrong.

## Verification

```bash
make check
uv run python -c "from lakehouse.session import build_session; s = build_session(); print(s.version)"
STORAGE_ROOT=./warehouse-alt uv run pytest tests/test_session.py -q
ls warehouse-alt/            # the seam actually moved the data
```

The `STORAGE_ROOT` override is the point of the phase. If a test writes to
`./warehouse` while the environment says otherwise, the seam leaks.

## Artifacts

- `src/lakehouse/session.py`
- `src/lakehouse/paths.py`
- `tests/test_session.py`
- `docs/adr/NNNN-<repo-structure-and-storage-seam>.md`
- `.gitignore` entry for `warehouse*/`

## Progress log

Dated appends only. Newest at the bottom.
