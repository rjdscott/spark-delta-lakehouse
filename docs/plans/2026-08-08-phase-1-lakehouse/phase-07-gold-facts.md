# Phase 07: Gold facts

## Goal

Three fact tables at three different grains, which is the point: a transaction
grain fact, a periodic snapshot, and an accumulating snapshot updated in place.
`fact_transaction` resolves each transaction to the dimension version current
at `txn_ts` through an as-of join on the effective range, with inferred members
for the accounts that arrive late.

Temporal correctness is the claim this phase has to earn. A transaction posted
five days after it occurred must resolve to the dimension version that was
current when it occurred, not the one current when it loaded. The generator
planted that case deliberately.

## Tasks

- [ ] `fact_transaction`: transaction grain, as-of join to `dim_party` and
      `dim_account` on the effective range containing `txn_ts`.
- [ ] Inferred members: a transaction referencing an account that first appears
      in a later batch gets a dimension member created for it, flagged as
      inferred, and reconciled when the real record arrives.
- [ ] `fact_daily_balance`: periodic snapshot, one row per account per day.
- [ ] `fact_account_lifecycle`: accumulating snapshot, multiple milestone dates
      updated in place as they occur.
- [ ] Grain declared in spec, docstring and table comment, all three agreeing.
- [ ] Tests: grain uniqueness on every fact; zero orphan surrogate keys;
      temporal correctness on the late-posted transaction specifically, not on
      a happy-path row; inferred members reconcile rather than duplicate.
- [ ] ADR: inferred member handling. The rejected options include dropping
      orphans and deferring them to a later run.
- [ ] ADR: snapshot versus derived balances. State what the snapshot costs in
      storage and what deriving would cost at query time.

## Verification

```bash
make check
uv run python -m lakehouse.gold --tables fact
uv run pytest tests/test_facts.py -q

# the case that matters, run and read by hand
uv run pytest tests/test_facts.py::test_late_posted_resolves_at_event_time -q
```

Pick one late-posted transaction and follow it by hand from source CSV to fact
row before calling this done. If the as-of join is wrong, the row count will
not tell you.

## Artifacts

- `src/lakehouse/gold/fact_transaction.py` and siblings
- `src/lakehouse/gold/asof.py`
- `tests/test_facts.py`
- two ADRs, inferred members and snapshot versus derived

## Progress log

Dated appends only. Newest at the bottom.
