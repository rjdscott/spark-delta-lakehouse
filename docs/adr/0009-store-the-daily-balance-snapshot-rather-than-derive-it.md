# 0009. Store the daily balance snapshot rather than derive it

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

`fact_transaction` records movement. "What was this account's balance on the
14th" is not answerable from movement alone without a running total, and a
running total over an account's whole history is an expensive thing to ask
every consumer to write correctly.

The three fact tables in this repo exist to show that grain is a choice rather
than a consequence: a transaction-grain fact, a periodic snapshot, and an
accumulating snapshot answer different questions about the same business
process, and none of them is a worse version of another.

## Options considered

**A. Derive balances at query time** from `fact_transaction` with a window
function.
- Pros: no storage, no second pipeline, one source of truth.
- Cons: every consumer rewrites the same window and some get it wrong,
  particularly around days with no movement. Answering "balance on a date"
  requires scanning the account's entire history, so the cost grows with age
  rather than with the question.

**B. Store a periodic snapshot,** one row per account per open day.
- Pros: the question becomes a point lookup. Days with no transactions exist as
  rows, which is what makes "balance on the 14th" answerable at all without
  reconstruction. It is the standard treatment for a balance.
- Cons: 288,310 rows for 3,165 accounts over 96 days, and the row count grows
  every day whether anything happened or not. Rebuilding is a full recompute.

**C. Store closing balances only on days with movement.**
- Pros: far fewer rows.
- Cons: it is option A wearing a table. The consumer still has to find the most
  recent row on or before the date, which is the reconstruction the snapshot
  exists to remove.

## Decision

**We will store a periodic daily snapshot, including rows for days with no
movement.** The quiet rows are 229,785 of the 288,310, four in five, and they
are the reason the grain is worth having.

Days outside an account's life are not stored. A snapshot of an account that
did not exist yet is not a zero balance, it is not a fact.

## Consequences

Balance questions are point lookups and the arithmetic is done once, in one
place, by code that is tested. Continuity is checkable and checked: yesterday's
closing balance equals today's opening balance for every account-day, and the
final closing balance equals the sum of movements.

The table is two orders of magnitude larger than the accounts it describes, and
grows daily regardless of activity. At 3,165 accounts this is trivial; at
millions it is the dominant table in the warehouse and would want partitioning
by date and a retention policy, neither of which is built here.

A correction to a historical transaction requires recomputing every subsequent
day for that account, because balances carry forward. That is inherent to
storing a cumulative position rather than deriving it, and it is the real price
of option B.

**Revisit when:** the daily row count makes a full recompute impractical, at
which point the snapshot wants incremental maintenance from the last stored day
rather than a rebuild.

## Related

- [ADR 0006](0006-coherence-over-fidelity-in-synthetic-data.md), which gave
  accounts a brought-forward balance so a cumulative sum means something.
- `docs/plans/2026-08-08-lakehouse-on-minio/phase-08-gold-star-schema.md`.
