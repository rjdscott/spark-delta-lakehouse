# 0007. A vanished party closes its timeline

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

Party extracts are full snapshots, so a party that stops appearing has been
removed at the source. Defect 7 plants twenty-five of them: present in batch 1,
absent from batch 2 onward.

Silver has to decide what that absence means. The decision matters because
`dim_party` is built on it and because "how many customers do we have" is
answered from `is_current`.

Absence is only information when presence is guaranteed. In the transaction
stream, which is incremental, a missing row means nothing at all. So whatever
is decided has to be a declared property of the entity rather than a rule
applied everywhere.

## Options considered

**A. Close the current version.** Set `effective_to` to the batch timestamp and
`is_current` to false. No new row, no new column.
- Pros: uses the machinery SCD2 already has. Historical versions stay intact,
  so a transaction from before the deletion still resolves to the version
  current at its event time. Counting current parties is correct without any
  query needing to know about deletion.
- Cons: the timeline records *that* we stopped knowing about the party, not
  *why*. A source outage that drops rows looks identical to a deletion.

**B. Insert a tombstone version** carrying an `is_deleted` flag.
- Pros: the reason is explicit and queryable.
- Cons: adds a column that exists for one entity, which is exactly what the
  spec guardrail forbids. It also makes `is_current` ambiguous: there is now a
  current row for a party that does not exist, and every downstream count has
  to remember to filter it.

**C. Leave the last version standing as current.**
- Pros: nothing to build.
- Cons: silently wrong. Deleted parties are counted as customers forever, and
  the error is invisible because the data looks complete.

## Decision

**We will close the current version of a party that disappears from a snapshot
extract, and record nothing else.** The entity declares whether absence is
meaningful, through `absence_means_deletion` in its spec, so the rule is a
property of the model rather than a behaviour hidden in the builder.

Option B is rejected specifically on the guardrail: a field that would appear
in exactly one spec does not belong in the schema.

## Consequences

Counting current parties is correct without any consumer knowing that
deletions exist. Historical resolution is unaffected: the versions that were
current when a transaction occurred are still there, still effective-dated, so
gold's as-of join finds them.

The cost is that a source failure is indistinguishable from a deletion. If an
extract truncates, silver will faithfully close every missing party and the
timeline will say those customers left on that day. Nothing here detects that,
and the mitigation is operational rather than modelled: an extract whose row
count collapses should fail before it reaches silver.

A reopened party, absent in one batch and present in the next, gets a fresh
version with a gap in its timeline. That is the honest representation of what
was known, and gold must not assume a party's versions are contiguous.

**Revisit when:** a source distinguishes a deletion from a suppression, or when
an extract failure causes a false mass-deletion. The first would justify
option B with a real reason code; the second is a signal to guard the load.

## Related

- `data/DEFECTS.md` defect 7, the case this decision answers.
- [ADR 0006](0006-coherence-over-fidelity-in-synthetic-data.md) for why the
  snapshot and incremental extract shapes differ in the first place.
