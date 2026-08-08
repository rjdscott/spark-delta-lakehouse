# 0006. Coherence over fidelity in synthetic data

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

The first generator drew every field independently: transaction amounts from a
uniform distribution regardless of type, merchant categories regardless of
product, suburbs regardless of state. Review-03 found the consequence.
Debits were positive as often as negative, so summing `amount` meant nothing,
and any business example built on it, spend by category, daily balances,
account lifecycle, would have produced a chart that was obviously wrong to
anyone watching.

The question is how much realism synthetic data needs. Too little and the demo
collapses under the first business question. Too much and the generator becomes
a simulation project that teaches nothing about dimensional modelling.

## Options considered

**A. Leave it random.** The pipeline does not care about values.
- Pros: no work; the modelling machinery is unaffected.
- Cons: every gold table is unreadable. A fact table nobody can sanity-check
  is a fact table nobody trusts, and the repo is meant to be read.

**B. Coherence: every number must make sense against the row next to it.**
Sign conventions, opening balances, product-appropriate categories, geography
that agrees with itself, no activity on closed accounts.
- Pros: business examples become legible without simulating a bank. Several
  of the constraints are also genuine referential rules the pipeline must
  preserve, so they double as test material.
- Cons: a table of product profiles and category ranges to maintain, and the
  temptation to keep adding realism.

**C. Statistical fidelity.** Match real distributions for spend, income,
default rates, seasonality.
- Pros: the most convincing demo.
- Cons: an open-ended modelling project with no end state, teaching nothing
  about the thing this repo is about. Nobody will check it against real data,
  and if they did, being wrong would not matter.

## Decision

**We will generate data that is internally coherent and make no attempt at
statistical fidelity.** The test is whether a number survives comparison with
the row next to it, not whether it matches the real world.

Concretely: debits and fees are negative and credits and interest positive;
every account opens with a deposit so a running balance is a real cumulative
sum; merchant categories fit the product; transactions occur only while an
account is open; suburb, state and postcode travel together; most parties hold
one or two accounts rather than a uniform draw.

Deliberately not simulated: interest accrual formulas, fraud patterns, foreign
exchange, fee schedules, seasonality.

## Consequences

Gold tables become legible. `fact_daily_balance` is a cumulative sum from a
real opening balance rather than a random walk, and spend by merchant category
is a chart someone can read.

Four of the coherence rules are now enforced by tests, which means they are
also integrity rules the pipeline must not break. That is a bonus rather than
the intent, but it is where the coherence constraints earn their keep twice.

The generator is longer and carries a product profile table. Every future
product or category needs an entry, and the pull toward more realism will be
constant. The list of what is deliberately not simulated exists to resist it.

The seed is unchanged, but the data is entirely different, so any analysis or
screenshot taken before this decision is stale.

**Revisit when:** someone asks a business question the data cannot answer
coherently. That is a reason to extend the profiles, not to pursue fidelity.

## Related

- [review-03 M-04](../audits/2026-08-08-review-03/01-code-and-model.md#m-04),
  which found the missing sign convention.
- `data/DEFECTS.md`, which documents what is wrong with the data on purpose,
  as distinct from what is coherent about it on purpose.
