# 0011. The SCD2 rebuild reads bronze, not the stored table

- **Status:** Accepted
- **Date:** 2026-08-11

## Context

The SCD2 build rebuilds a key's whole timeline on every batch that touches
it, and prunes versions whose tracked fingerprint equals their predecessor's.
The rebuild needs a source for "every version known for this key". Until now
that source was the stored silver table, unioned with the incoming batch.

The stored table is lossy by design: it holds only rebuild survivors. A
pruned no-op stops being a no-op the moment a later batch delivers an
out-of-order tracked change between it and its predecessor; the true history
is then X, Y, X, three versions, and a rebuild that cannot see the pruned
row produces two versions ending on Y. Which answer you get depends on the
order the batches were processed. Review-07 H-09 demonstrated this with a
three-batch counterexample in which the in-order run, the one `make demo`
performs, is the wrong one, and found the drop mechanism live in the shipped
data (one of P000011's versions pruned from silver while bronze still holds
it).

This is the same force ADR 0010 resolved for deletions one batch earlier:
state that survives only in a written-once form loses to a rebuild. Bronze
is append-only, holds every version ever landed with `replaceWhere`
idempotency per batch, and is already read by the deletion derivation.

## Options considered

**A. Keep sourcing from the stored table, retract the universal convergence
claim.**
- Pros: no code change; the shipped data currently converges.
- Cons: "converges under any replay order provided no no-op precedes a late
  arrival" is not a property anyone can operate; the caveat is exactly the
  kind of footnote that reads as a bug the day it fires. The claim is the
  repo's headline.

**B. Stop pruning no-op versions, store them all.**
- Pros: the stored table becomes lossless and could stay the source.
- Cons: gives up the property that a version means a change; a full-snapshot
  source then grows the dimension by one row per key per batch, the exact
  failure the module docstring calls out. Every gold as-of join pays for it.

**C. Source the rebuild from bronze for the affected keys.**
- Pros: every build of a key becomes a pure function of the full landed
  history, so replay order cannot matter, by construction rather than by
  proof over one dataset. Symmetric with ADR 0010; bronze is already on the
  build's read path for deletions.
- Cons: the per-key read scans all bronze batches instead of the stored
  survivors, and bronze rows re-coerce on every rebuild. Both are bounded by
  the affected-key semi-join, but the cost grows with batch count.

## Decision

**We will source the SCD2 rebuild from bronze, semi-joined to the affected
keys, because a rebuild is only order-independent if its input does not
depend on the order.** The stored table remains the merge target and the
serving surface; it is no longer an input to its own reconstruction. Scope:
the silver SCD2 build; SCD1 entities keep their merge path.

A consequence made explicit while deciding this: untracked attributes are
frozen at the version that opened them. A later row changing only untracked
attributes is pruned, so the correction leaves no trace and `tracked: false`
does not mean type 1 overwrite. That is deliberate, cheap to change later
precisely because of this ADR (a semantics change is a code edit plus a
rebuild from bronze), and pinned by
`test_untracked_change_opens_no_version`.

## Consequences

Easier: the convergence claim is structural, and the replay proof becomes a
regression check rather than the argument. Replaying any batch, including
batch 1 after a full run, reconstructs identical timelines
(fingerprint-verified in order and as 3,1,2). The counterexample is pinned
in `test_a_pruned_no_op_revives_when_a_late_arrival_lands_between`.

Harder: the build reads more data per affected key, and silver can no
longer be rebuilt from silver alone; bronze retention is now load-bearing
for correctness, not just for audit. Committed to: bronze as the system of
record for dimension history, which is what ADR 0009 and 0010 already
assumed.

**Revisit when:** a bronze entity exceeds roughly 100 batches or the
per-key history no longer fits the executor comfortably; at that point the
rebuild wants a compacted all-versions intermediate (the same successor
table ADR 0010's derivation would need at scale).

## Related

- [ADR 0010](0010-deletion-derives-from-the-snapshot-stream.md): the same
  argument for deletion state; this ADR applies it to attribute versions.
- [ADR 0009](0009-store-the-daily-balance-snapshot-rather-than-derive-it.md),
  [ADR 0008](0008-the-first-version-of-a-dimension-starts-at-the-beginning-of-time.md):
  the rebuild semantics this preserves.
- Review-07 H-09
  (`docs/audits/2026-08-10-review-07/01-findings.md#h-09`): the
  counterexample and the live evidence.
