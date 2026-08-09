# Findings: code, model, tests

Audited at `d79bda4`. Every finding reproduced.

<a id="h-01"></a>
## H-01: the same-day-change test passes by dictionary ordering

`tests/test_generate.py::test_defect_2_a_party_changes_address_twice_in_one_day`
counts `(party_id, date)` pairs with two or more **rows**, then asserts on the
first one it finds. But defect 1 plants exact duplicate rows, and a duplicated
party produces two rows on the same date without having changed at all.

**Evidence.** Of the eleven candidates the test could select in batch 1, ten
are duplicates rather than real changes:

```
candidates for test_defect_2: 11
  P000007 2026-01-15: distinct stamps=2 -> REAL same-day change
  P000439 2026-01-15: distinct stamps=1 -> DUPLICATE, not a change
  P000763 2026-01-15: distinct stamps=1 -> DUPLICATE, not a change
  ...
first candidate is: ('P000007', '2026-01-15')
```

It passes today because `P000007` happens to be first in insertion order. Any
change to the seed, the duplication rate, or the row order moves a duplicate
to the front, and the second assertion then fails.

**Impact.** The defect that forces timestamp-grained SCD2 ranges is the single
hardest thing this repo has to get right, and its guard is currently a
coincidence. It will fail confusingly later, or worse, keep passing while the
defect stops being planted.

**Fix.** Select on distinct `updated_at` values, not on row count: a real
same-day change has two distinct timestamps on one date, a duplicate has one.

<a id="h-02"></a>
## H-02: bronze specs declare coerced types, which is silver's job

The brief is explicit that bronze is "source-shaped ... no dedupe, no renaming,
no business logic", and that type coercion belongs to silver. The bronze specs
do it anyway.

**Evidence.** `model/bronze_*.yml`:

```
- {name: open_date,  type: date,           tracked: false}
- {name: txn_ts,     type: timestamp,      tracked: false}
- {name: amount,     type: "decimal(18,2)", tracked: false}
```

The sources are CSV. Every value arrives as text. Declaring `decimal(18,2)` in
bronze means either the read coerces, which is business logic in the raw layer,
or the declaration is a lie the DDL will enforce and the load will fail on.

**Impact.** This is the exact discipline failure the repo's thesis argues
against, committed in the repo's own model. It also destroys bronze's purpose:
a row that fails coercion has nowhere to land, so a malformed value becomes a
pipeline crash rather than a rescued record.

**Fix.** Bronze attributes are all `string`. Silver's specs already declare the
real types, which is where coercion belongs. This also makes the rescued-data
column meaningful.

<a id="h-03"></a>
## H-03: a spec can silently disagree with the table it generated

`ddl.create_table` emits `CREATE TABLE IF NOT EXISTS`. Editing a spec after the
table exists produces no change and no warning. Nothing anywhere compares a
physical table to its spec.

**Impact.** The entire claim of this design is that physical tables are derived
and therefore cannot drift. Right now they are derived exactly once and can
drift freely afterwards. The spec conformance test is listed in phase 09, which
is after every table has been built and possibly edited.

**Fix.** Bring the conformance check forward to phase 05, where the first
tables are created: compare declared columns, types and table properties
against `DESCRIBE`. It is the test that makes the spec load bearing rather than
decorative, and it is worth little written last.

<a id="m-04"></a>
## M-04: transaction amounts have no sign convention

`amount` is drawn from a uniform distribution independent of `txn_type`, so
debits are positive as often as negative.

**Evidence.**

```
CREDIT    {'pos': 2141, 'neg': 2207}
DEBIT     {'pos': 2099, 'neg': 2152}
FEE       {'pos': 2033, 'neg': 2114}
INTEREST  {'neg': 2205, 'pos': 2134}
```

**Impact.** Any business example built on this is nonsense: spend by merchant
category, daily balances, account lifecycle values. `fact_daily_balance` in
particular becomes a random walk with no opening balance, which will look
obviously wrong on a chart in front of an audience.

**Fix.** Give the generator a sign convention (debits and fees negative,
credits and interest positive) and an opening balance per account, and state
the convention in `data/DEFECTS.md`. Realism is not the goal; coherence is.

<a id="m-05"></a>
## M-05: the package is not installable, so imports depend on the caller

**Evidence.** `uv run python -c "import lakehouse"` fails with
`ModuleNotFoundError`. `pyproject.toml` has no `[build-system]`, so `uv sync`
never installs the project. Three different places compensate differently: the
`Makefile` sets `PYTHONPATH=src`, `pyproject.toml` sets pytest's `pythonpath`,
and the container sets `ENV PYTHONPATH=/opt/lakehouse/src`.

**Impact.** Three mechanisms that must agree and nothing that makes them.
A contributor running a script directly gets an import error that none of the
documentation predicts.

**Fix.** Add a build system and declare the package. One mechanism, works
everywhere, deletes three workarounds.

<a id="m-06"></a>
## M-06: `source` means two different things

In bronze specs, `source: party` names a raw CSV. In silver specs,
`source: bronze_party` names another spec. `spec.py` even branches on the
layer to decide whether to validate it:

```python
if spec.source and spec.layer != "bronze":
    _require(spec.source in specs, ...)
```

**Impact.** One field with two meanings and a layer-dependent validation rule
is exactly the kind of quiet ambiguity that makes a schema hard to extend. The
next entity added will pick the wrong meaning.

**Fix.** Two fields: `source_file` for bronze, `source_spec` for derived
layers. Then validation is unconditional and the branch disappears.

<a id="m-07"></a>
## M-07: MinIO credentials are duplicated in four files

`docker/.env`, `docker/uc/server.properties`, `docker/hive/core-site.xml` and
the runbook each carry `lakehouse123` independently. Changing one leaves three
wrong, and the failure surfaces as an opaque 403.

**Fix.** Keep `docker/.env` as the source, template the rest, or at minimum
add a check. Also worth splitting `.env`: the version pins are documentation
that must be committed, the credentials are habit-forming to commit.

<a id="m-08"></a>
## M-08: the settlement-lag test does not test the lag it claims

`test_defect_5_settlement_lags_the_event_by_up_to_five_days` asserts only that
some transaction posts on a later day and that settlement never precedes the
event. The five-day bound in the name is never checked, so a generator change
to a fifty-day lag would pass. The set-membership construction
(`lags = {...}; assert True in lags`) also obscures a plain `any()`.

**Fix.** Assert the bound explicitly: `0 <= (posted_ts - txn_ts) <= 5 days`.

<a id="l-09"></a>
## L-09: the smoke test reaches into private Spark internals

`scripts/smoke_stack.py` calls
`spark.sparkContext._jsc.sc().schedulerBackend().getExecutorIds()`. That is a
private path across a JVM bridge and will break on a Spark upgrade. The public
`sparkContext.statusTracker().getExecutorInfos()` says the same thing.

<a id="l-10"></a>
## L-10: small cleanliness in `ddl.py` and `spec.py`

`ddl.columns` re-packs tuples that are already the right shape
(`[(n, t, c) for n, t, c in LINEAGE_COLUMNS]`). `spec.py` imports
`dataclasses.field` solely to write `field(default=())` where `= ()` would do.

<a id="l-11"></a>
## L-11: no automated verification of the pipeline exists

CI runs `make check`: docs, lint, unit tests. Nothing exercises Spark, Delta,
MinIO or the metastore, because CI has no Docker. `make stack-smoke` is the
only proof the platform works and it is run by hand.

Not a defect so much as an unstated limit. It should be stated, because "31
tests passing" currently reads as more coverage than it is.
