# 0010. Deletion derives from the snapshot stream, not from the batch in hand

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

ADR 0007 decided that a party absent from a snapshot extract has its current
version closed. The mechanism it got was `close_vanished`: compare the batch
being processed against the current rows, close whatever is missing.

Review-06 C-01 proved that mechanism unsound, by reproduction. The SCD2
timeline rebuild reads a key's attribute rows only, so a closure is not part
of what a rebuild sees, and `close_vanished` runs against a single batch, so
replaying batch 1 after a full run resurrected all 25 deleted parties
(current count 1,975 to 2,000). The convergence proof in phase 07 used replay
order 3,1,2, the one permutation that ends on the batch that re-closes the
deleted set. Convergence held for attribute versions and failed for closures.

The root problem: deletion was **state written once**, while every other fact
in the silver layer is **derived from bronze and therefore recomputable**.
Anything that is state-written-once loses to a rebuild.

Review-06 M-02 compounds it: an empty extract made `close_vanished` close the
entire dimension with exit code 0, a failure ADR 0007 explicitly named and
never guarded.

## Options considered

**A. Keep the mechanism, re-run `close_vanished` for every batch ever seen
after each build.**
- Pros: minimal code change.
- Cons: ordering logic in the builder ("which batches, in what order")
  reimplements exactly the history bronze already stores, badly.

**B. Represent deletion as a tombstone row in the version stream,** so the
rebuild itself carries it.
- Pros: the rebuild becomes the single mechanism; closures survive by
  construction.
- Cons: ADR 0007 already rejected tombstones for good reasons: a current row
  for a nonexistent party, a flag column only one entity uses, every count
  needing a filter.

**C. Derive deletion from bronze at every build.** A key is deleted when it
is absent from the latest landed snapshot; its deletion date is the first
batch it went missing from. Recompute this set after every rebuild and
re-apply the closures.
- Pros: deletion becomes derived state like everything else, so it converges
  under any replay order by construction: bronze holds every batch, and the
  derivation does not depend on which batch is being processed. Idempotent
  re-application costs one MERGE against rows that are already closed.
- Cons: reads all of bronze's key/batch pairs on every build. Trivial here;
  at scale it wants the last-seen aggregate maintained incrementally.

## Decision

**We will derive the deleted set from the full snapshot stream in bronze on
every SCD2 build, and re-apply closures after every timeline rebuild.**
Deletion is a trailing absence: a key missing from the latest landed snapshot
is deleted, dated at the first batch it failed to appear in.

Two consequences of ADR 0007 are explicitly retracted:

1. **There is no gap for a reappearing party.** A key absent from one
   snapshot and present in a later one was never deleted under trailing-
   absence semantics; its timeline is continuous. ADR 0007 promised a gap;
   the mechanism never produced one, and this decision stops pretending
   otherwise. Absence windows in the middle of the stream are not recorded.
2. **The guard is now mandatory, not aspirational.** A build whose incoming
   snapshot is empty refuses to run. An empty extract is a source failure,
   not a mass deletion, exactly as ADR 0007 argued without enforcing.

ADR 0007's core decision survives unchanged and is carried forward by this
ADR: a vanished party closes its timeline, no tombstone row, no flag column,
`absence_means_deletion` declared on the entity.

## Consequences

Replay converges in any order, closures included, and the convergence test
now runs an order that ends in batch 1, the order that caught the defect.

Deletion dates can shift under pathological bronze states: if a batch lands
empty (guarded against) or is removed from bronze, the derived dates move
with the evidence. That is the nature of derived state, and it is the honest
answer: the deletion date was always an inference from absence.

Every SCD2 build now scans bronze's key and batch columns for the entity.
At 6,000 rows this is nothing; at hundreds of millions the last-seen
aggregate wants incremental maintenance, and that threshold is the revisit
trigger.

**Revisit when:** bronze grows large enough that the per-build scan is
measurable, or when a source can distinguish deletion from suppression, which
would justify recording mid-stream absence windows.

## Related

- [ADR 0007](0007-a-vanished-party-closes-its-timeline.md), superseded by
  this ADR: the decision survives, the mechanism and the gap consequence do
  not.
- [review-06 C-01](../audits/2026-08-09-review-06/01-findings.md#c-01), the
  reproduction that forced this.
