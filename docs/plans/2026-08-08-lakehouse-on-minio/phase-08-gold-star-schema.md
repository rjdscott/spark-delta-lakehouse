# Phase 08: Gold star schema

## Goal

Conformed dimensions and a transaction-grain fact, built on silver, with hash
surrogate keys and event-time resolution.

## Tasks

- [x] Gold specs, written now that the fields are known rather than guessed.
- [x] `surrogate_key: hash` declared in the spec; inputs derived from the
      business key plus `effective_from` where history is kept.
- [x] `dim_party` carrying the SCD2 effective ranges through from silver.
- [x] `dim_account` with inferred members for orphan references.
- [x] `dim_merchant_category` with a member for the nulls defect 6 plants.
- [x] `dim_date` generated across the range the facts need.
- [x] `fact_transaction` resolved by as-of join on `txn_ts`.
- [x] `scripts/verify_gold.py`.
- [x] `fact_daily_balance`, a periodic snapshot including quiet days.
- [x] `fact_account_lifecycle`, an accumulating snapshot updated in place.
- [ ] Unknown-party member for the 294 residual null keys.

## Verification

```bash
make gold
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_gold.py
```

Expected:

```
fact grain          : rows=75,918 distinct txn_id=75,918 OK
party_sk               orphan keys=     0  null keys=   294
account_sk             orphan keys=     0  null keys=     0
merchant_category_sk   orphan keys=     0  null keys=     0
date_key               orphan keys=     0  null keys=     0
facts via UNKNOWN category: 15,140
multi-version parties: facts=14,644 inside effective range=14,644
  of those, resolved to a NON-current version: 12,967
late-settling facts : 23,764
```

The line that matters is the last pair. Every fact belonging to a party with
more than one version falls inside the effective range it was joined on, and
12,967 of them resolved to a version that is **not** current. A lazy join to
`is_current` would produce a different and wrong answer for all of them, which
is what makes the SCD2 work in phase 07 worth its cost.

## Artifacts

- `model/gold_*.yml`, `src/lakehouse/gold.py`
- `scripts/run_gold.py`, `scripts/verify_gold.py`
- `docs/adr/0008-the-first-version-of-a-dimension-starts-at-the-beginning-of-time.md`

## Progress log

2026-08-09: Star schema built and queryable. dim_party 2,424 versions,
dim_account 3,165, dim_merchant_category 8, dim_date 96, fact_transaction
75,918 with grain holding and zero orphan surrogate keys on all four
relationships.

The finding worth the phase: the first build had 27,816 facts, 37 percent, with
a null `party_sk`. Referential integrity was clean and the grain was correct,
so every check passed while more than a third of the fact table pointed at
nothing. The cause was the early-arriving fact problem: each party's earliest
version began when the first extract mentioned them, while the transaction
stream starts thirty days earlier. ADR 0008 starts the earliest version at the
beginning of time, and the nulls fell to 294.

Three things are deliberately unfinished rather than quietly missing:

- **294 null `party_sk` remain.** They belong to accounts whose party was
  deleted, whose timeline closes per ADR 0007, leaving later transactions
  uncovered. The answer is an unknown-party member, not a null.
- **Inferred members are implemented but not exercised** in the current end
  state, because silver holds every batch and therefore every account. They
  appear when the layers are advanced batch by batch, which is what a daily run
  does and what the demo in phase 09 should show.
2026-08-09, later: both remaining grains built. `fact_daily_balance` at
288,310 account-days with 229,785 of them quiet, zero continuity breaks, zero
balance mismatches against the sum of movements, and no day outside an
account's life. `fact_account_lifecycle` at 3,165 rows with milestones in
order, 106 accounts that never transacted and 2,878 still open. ADR 0009
records why the snapshot is stored rather than derived.

The business queries found what the integrity checks could not. Every check
passed while "spend by merchant category" reported 80 million dollars of
Unknown spend across 3,001 transactions, an average of 27,000 each against
440 for Health. The brought-forward balances and the loan repayments were
typed as ordinary debits, so a balance carried into the window counted as a
purchase. Two fixes: a brought-forward balance is now its own `OPENING` type
carrying the sign of its product, and the category dimension distinguishes
`UNKNOWN`, meaning the source did not say, from `NOT_APPLICABLE`, meaning a
salary credit has no merchant. Unknown spend fell to 1.79 million across
2,289 transactions, and the ranking is now legible.

That is the third time in this build that a table passed every structural
check while answering a business question wrongly. Grain, referential
integrity and null counts do not detect a category error. Running a real query
does.
