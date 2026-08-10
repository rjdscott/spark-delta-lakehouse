# Seeded defects

`src/lakehouse/generate.py` plants these on purpose. A pipeline that only ever
sees clean data proves nothing, so each defect exists to force a specific
behaviour somewhere downstream.

Every defect has a test in `tests/test_generate.py` asserting it is still
present. If a defect stops being planted, the test that proves the pipeline
handles it would start passing for the wrong reason.

## What is coherent on purpose

Separately from the defects, the data is internally consistent, because a
business example built on incoherent numbers is worse than no example. See
[ADR 0006](../docs/adr/0006-coherence-over-fidelity-in-synthetic-data.md).

| Rule | Why it matters | Test |
|------|----------------|------|
| Debits and fees negative, credits and interest positive | summing `amount` means something | `test_amount_sign_agrees_with_transaction_type` |
| Balances are plausible for the product | a credit card has a limit; an everyday account is not permanently overdrawn | `test_balances_are_plausible_for_the_product` |
| A dormant account is quiet, not dead | status is current state, transactions are history | `test_a_dormant_account_is_quiet_not_dead` |
| Merchant categories fit the product | a home loan does not buy groceries | `test_merchant_categories_fit_the_product` |
| No activity after an account closes | the accumulating snapshot stays coherent | `test_no_transactions_after_an_account_closes` |
| Suburb, state and postcode agree | an address is not fiction | `test_geography_is_internally_consistent` |

Not simulated, deliberately: interest accrual formulas, fraud patterns,
foreign exchange, fee schedules, seasonality.

## Extract shapes

The three sources are not extracted the same way, and the difference is load
bearing:

| Source | Shape | Why |
|--------|-------|-----|
| `party` | full snapshot per batch | a hard delete is only detectable as an absence, which requires a full extract |
| `account` | full snapshot per batch | same, and it keeps late-arriving records expressible |
| `transaction` | incremental event stream | events are facts about a moment; they are not restated |

## The defects are disjoint

No party carries two defects. They overlapped once: the deleted set included
the parties emitting the same-day change and the out-of-sequence record, whose
extra rows bypass the snapshot filter, so those parties were deleted and still
emitting versions and only 23 of 25 deletions actually happened. Each defect
tested alone still passed. Defects that overlap stop testing what they claim.

## The eight

### 1. Exact duplicate rows, every source, every batch

Roughly one row in 200 is repeated verbatim.

**Exercises:** deduplication on the business key in silver. The naive fix,
`DISTINCT`, is wrong here: it would also collapse two legitimate versions of a
party that differ only in `updated_at`, which defect 2 depends on.

**Proven by:** `test_defect_1_exact_duplicate_rows_in_every_source`

### 2. A party changes address twice within the same day

One party emits two versions on the same date, at 11:15 and 16:45.

**Exercises:** SCD2 effective ranges must be timestamp-grained, not
date-grained. A `DATE` effective_from collapses these two versions into one,
or produces a zero-length range, and the party's history silently loses a
version.

**Proven by:** `test_defect_2_a_party_changes_address_twice_in_one_day`, which
selects on two *distinct timestamps* on one date rather than on two rows.
Defect 1 plants exact duplicates, so counting rows would let a duplicated
party satisfy this test without having changed at all.

### 3. Records arriving out of sequence

Batch 2 contains a party record whose `updated_at` is 45 days earlier than a
version already loaded from batch 1.

**Exercises:** the SCD2 builder must sequence by `updated_at`, not by arrival
order. A late record carrying stale state must not overwrite newer state, and
replaying batches in the wrong order must converge to the same final result.

**Proven by:** `test_defect_3_a_record_arrives_out_of_sequence`

### 4. Transactions referencing accounts that arrive in a later batch

Forty accounts are withheld from the batch 1 extract while batch 1 transactions
already reference them.

**Exercises:** inferred member handling in gold. The orphan references cannot
be dropped, because the transactions are real, and they cannot be resolved
normally, because the dimension member does not exist yet. A placeholder member
is created and reconciled when the real record arrives in batch 2.

**Proven by:** `test_defect_4_batch_1_transactions_reference_accounts_that_arrive_later`

### 5. Settlement lags the event by up to five days

`posted_ts` trails `txn_ts` by 0, 1, 2 or 5 days.

**Exercises:** temporal correctness in `fact_transaction`. The as-of join must
resolve to the dimension version current at `txn_ts`, the moment the
transaction occurred, not at `posted_ts` or at load time. This is the defect
that makes SCD2 worth having; without it, every join would be to the current
version and nobody would notice the difference.

**Proven by:** `test_defect_5_settlement_lags_the_event_by_up_to_five_days`

### 6. Nulls in `risk_rating` and `merchant_category`

About 4 percent of parties have no risk rating, about 3 percent of transactions
have no merchant category.

**Exercises:** null handling as a modelling decision rather than a filter. A
dimension needs a member for "unknown"; dropping the rows loses real
transactions, and leaving the null propagates into every downstream count.

**Proven by:** `test_defect_6_nulls_in_risk_rating_and_merchant_category`

### 7. Parties hard deleted between batches

Twenty-five parties present in batch 1 are absent from batch 2 onward. They
are chosen disjoint from the parties carrying defects 2 and 3.

**Exercises:** what silver does about a business key that stops arriving. In a
full snapshot the absence is information, and the answer is a real modelling
decision: close the current SCD2 version, flag the party as deleted, or leave
the last known version standing. Whichever is chosen gets an ADR, because all
three are defensible and they answer different questions.

**Proven by:** `test_defect_7_parties_are_hard_deleted_between_batches`

### 8. The batch 3 party extract carries a column the spec does not declare

Every batch 3 party row includes `marketing_consent`, a column no spec
knows about. The value is derived from the party id rather than the random
stream, so planting it changes nothing else in the data.

**Exercises:** bronze's `_rescued_data` path. An undeclared column must land
as JSON in the rescue column, not be dropped and not abort the load. Until
review-07 H-16 this branch threw `AnalysisException` on the exact input it
existed to survive, and no data had ever taken it.

**Proven by:** `test_defect_8_batch_3_party_extract_carries_an_undeclared_column`,
and `tests/test_bronze.py` exercises the rescue itself.

## Regenerating

```bash
make generate
```

The seed is fixed at 42. The same seed produces byte-identical files, asserted
by `test_same_seed_produces_identical_bytes`, so a reviewer can reproduce any
bug from the seed alone.
