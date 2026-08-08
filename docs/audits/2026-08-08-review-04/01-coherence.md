# Findings: the coherence rules that did not survive contact

Audited at `0b144af`. Every finding reproduced.

<a id="h-01"></a>
## H-01: 87 transactions occur on or after their account's close date

The rule is stated in `data/DEFECTS.md` and enforced by
`test_no_transactions_after_an_account_closes`, which passes.

**Evidence.** Checking all three batches rather than one:

```
transactions on/after close_date: 87
sample: txn_ts 2025-12-16 00:05:00, account closed 2023-10-19, SAVINGS
their txn_type: {'CREDIT': 84, 'DEBIT': 3}
```

Every one is the opening deposit. In `_transactions`, the opening deposit is
emitted *before* the `_active` guard, so an account closed years earlier still
receives one, dated at the start of batch 1.

The test misses it for a second, independent reason: it reads only
`BATCH_DATES[2]`. Two partial guards, and the gap between them is exactly
where the bug lives.

**Impact.** `fact_account_lifecycle` is an accumulating snapshot over account
milestones; a deposit after closure makes the milestone ordering incoherent.
It also breaks the claim in ADR 0006 that this data survives inspection.

**Fix.** Move the opening deposit inside the activity guard and date it at the
account's open date, not the batch start. Extend the test across all batches.

<a id="h-02"></a>
## H-02: credit card and transaction balances are not plausible

**Evidence.** Cumulative balance per account across all three batches:

```
CREDIT_CARD   n=  468 min= -64,586 med= -32,589 max=  -2,727
TRANSACTION   n= 1461 min= -28,861 med=  -4,561 max=  46,939
SAVINGS       n=  739 min=   1,525 med=  29,868 max=  99,924
TERM_DEPOSIT  n=  233 min=  11,090 med= 138,638 max= 306,753
HOME_LOAN     n=  148 min=-857,297 med=-504,311 max= -227,046
```

Savings, term deposit and home loan are all reasonable. The two everyday
products are not. A credit card with a median balance of minus thirty-two
thousand dollars has no limit; a transaction account whose median holder is
four and a half thousand dollars overdrawn is not an everyday account.

The cause is arithmetic, not conceptual: credit cards get 12 to 38 debits a
month against a single payment of 200 to 4000 at 80 percent probability, and
have no opening balance because their profile is `(0, 0)`. Transaction
accounts spend 18 to 45 times a month against one salary credit.

**Impact.** This is the number a viewer checks first, on the products they
understand best. It also makes `fact_daily_balance` misleading rather than
merely synthetic.

**Fix.** Give credit cards a limit and a payment sized to the period's spend.
Balance the transaction account's spend against its salary so the median
holder drifts slightly positive.

**Root note.** The balance rule is the only one of the five coherence rules in
`data/DEFECTS.md` with no test; its entry points at `fact_daily_balance`,
which does not exist. It is the rule that broke.

<a id="m-03"></a>
## M-03: a status change retroactively erases an account's history

`_active` gates transaction generation on `account["status"] != "DORMANT"`,
evaluated against the account's *current* status.

**Evidence.** In batch 3, 625 accounts are dormant and none of them has ever
transacted in any batch, including batches where they were open:

```
accounts by status:     {'OPEN': 2256, 'DORMANT': 625, 'CLOSED': 284}
transacting by status:  {'OPEN': 2256, 'CLOSED': 35}
```

**Impact.** Status is a current attribute; transactions are historical events.
Using the former to decide the latter means an account that goes dormant in
March is retroactively silent in January. It is also the exact confusion the
repo's thesis is about, current state standing in for history, reproduced in
the generator.

**Fix.** Decide activity from the status the account held during the period,
or simply generate reduced activity for dormant accounts rather than none.

<a id="m-04"></a>
## M-04: 116 accounts have no transactions at all

**Evidence.** 3,165 accounts exist; 3,049 have any batch-1 transaction.

These are credit cards belonging to dormant or closed accounts, which get no
opening deposit because their profile opening range is `(0, 0)` and no
activity because of M-03. Their balance is undefined rather than zero.

**Impact.** Low on its own, but a dimension member with no facts is a
legitimate case gold must handle, so it should exist on purpose rather than by
accident.

<a id="carried"></a>
## Carried open from review-03

- **H-03**, spec conformance. Still nothing compares a physical table to its
  spec. Phase 05 creates the first tables, which is the moment this stops
  being theoretical.
- **M-07**, MinIO credentials duplicated across four files.
- **L-11**, CI covers docs, lint and unit tests only. Nothing exercises Spark,
  Delta, MinIO or the metastore.
