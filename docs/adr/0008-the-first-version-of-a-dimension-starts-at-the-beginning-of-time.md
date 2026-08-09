# 0008. The first version of a dimension starts at the beginning of time

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

`fact_transaction` resolves each transaction to the party version whose
effective range contains `txn_ts`. When gold was first built, 27,816 of 75,918
facts, 37 percent, had a null `party_sk`.

The cause was not a join bug. Each party's earliest version began at the
`updated_at` on the first extract that carried them, 2026-01-15. The
transaction stream starts thirty days earlier. So every transaction that
occurred before the first extract fell outside every version of its party, and
resolved to nothing: 27,522 of them.

This is the early-arriving fact problem. It is structural, not synthetic: any
first load of a warehouse has facts older than the first dimension extract,
because the business existed before the pipeline did.

## Options considered

**A. Leave the gap and route unmatched facts to an unknown member.**
- Pros: honest, in that the dimension genuinely does not know what the party
  looked like in December.
- Cons: 37 percent of a first load pointing at "unknown" makes the warehouse
  useless for exactly the period people most want to analyse, and the unknown
  member carries no attributes to group by.

**B. Start the earliest version at the beginning of time.** The first version
of a key is effective from a far-past sentinel rather than from the timestamp
we first saw it.
- Pros: every fact resolves to the earliest known state of its dimension, which
  is the best available answer. It is also the standard Kimball treatment.
- Cons: asserts that the attributes were true earlier than we can know. A party
  who moved house in December is shown at their January address for December
  transactions.

**C. Backfill dimension history from an earlier extract.**
- Pros: correct.
- Cons: there is no earlier extract. This is a real answer only when the source
  can supply history, and most cannot.

## Decision

**We will set the earliest version of each business key to be effective from
`1900-01-01`,** so that any fact predating the first extract resolves to the
earliest state we know about.

The distinction that justifies it: we know when we first *saw* an attribute,
not when it *became* true. Treating first sighting as the start of validity
asserts something we also do not know, and asserts it in the direction that
destroys 37 percent of the data.

## Consequences

Null `party_sk` fell from 27,816 to 294, and the remainder are a different
problem, recorded below.

Facts before the first extract are attributed to the party's earliest known
state. That is a stated approximation, not a claim of truth. Anyone measuring
attribute change over a period that begins before the first extract will see no
change, because none is recorded, and should not read that as stability.

The sentinel is visible in the data. A reader who sees `1900-01-01` should
understand it as "at least this long", not as a real date, and no consumer
should compute a duration from it.

Surrogate keys for first versions changed when this was applied, because the
hash includes `effective_from`. That is the hash strategy working as intended:
the inputs changed, so the keys changed, deterministically and everywhere at
once.

**Still open, and deliberately not fixed here:** 294 facts still have a null
`party_sk`. They belong to accounts whose party was deleted, whose timeline
closes at the deletion per ADR 0007, leaving later transactions uncovered. The
right answer is an unknown-party member rather than a null, and it is recorded
in the review punchlist rather than smuggled into this decision.

**Revisit when:** a source can supply dimension history predating the first
extract, which would make option C available and this sentinel unnecessary.

## Related

- [ADR 0007](0007-a-vanished-party-closes-its-timeline.md), whose closed
  timelines produce the 294 residual nulls.
- `data/DEFECTS.md` defect 5, which makes event-time resolution observable.
