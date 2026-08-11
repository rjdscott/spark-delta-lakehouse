# Phase 07: Silver SCD2 party

## Goal

Party as SCD Type 2: one row per business key per version of its tracked
attributes, effective-dated on a timestamp range, converging to the same final
state under any replay order.

## Tasks

- [x] ADR 0007 for the open fork: what a vanished party means.
- [x] `absence_means_deletion` declared on the entity, unconditionally, so the
      rule is a property of the model rather than a layer-dependent branch.
- [x] Timeline rebuild per affected key, from stored versions unioned with
      incoming ones.
- [x] Timestamp-grained effective ranges, half open.
- [x] Only tracked attributes open a version.
- [x] Close the current version of a party absent from a snapshot extract.
- [x] `make party`, `scripts/verify_scd2.py`.

## Verification

```bash
make party
docker compose -f docker/compose.yaml --env-file docker/.env exec -T app \
  /opt/spark/bin/spark-submit --master spark://spark-master:7077 scripts/verify_scd2.py
```

Expected (refreshed 2026-08-10 with the review-07 P0 fixes; the fence is
byte-comparable to real output, commentary sits below it):

```
overlapping ranges  : 0
timeline gaps       : 0
inverted ranges     : 0
keys with >1 current: 0
keys with 0 current : 25  (deleted parties, ADR 0010)
vanished per bronze : 25  OK
same-day versions   : 2 keys
versions per party  : min=1 max=6 mean=1.22
no-op versions      : 0
```

The 25 zero-current keys are the deleted parties and are correct. Same-day
keys fell from 3 to 2 when ADR 0008's 1900-01-01 sentinel moved every first
version off its batch date; the `inverted ranges` line was added by
review-06 M-12.

Convergence, which is the property the design was chosen for. Drop
`silver.party`, replay the batches as 3, 1, 2, and compare (refreshed
2026-08-10 on the review-07 data; the fingerprint is
`sum(abs(xxhash64(all columns as string))) mod 10^13`):

```
in order      ROWS 2430 CURRENT 1975 FINGERPRINT 9070861178151
out of order  ROWS 2430 CURRENT 1975 FINGERPRINT 9070861178151
```

In the 3,1,2 replay the 25 deletions land during the batch-1 step, because
the derivation reads the whole snapshot stream rather than the batch being
processed (ADR 0010). Review-07 H-09 showed the attribute-version half of
this proof was order-lucky while the rebuild read the lossy stored table;
ADR 0011 moved the rebuild's source to bronze, which makes convergence
structural, and the counterexample is pinned in `tests/test_scd2.py`. The
replay above is now a regression check, not the argument.

## Artifacts

- `src/lakehouse/scd2.py`, `scripts/run_scd2.py`, `scripts/verify_scd2.py`
- `docs/adr/0007-a-vanished-party-closes-its-timeline.md`

## Progress log

2026-08-09: Completed. 2,424 rows for 2,000 parties, 1,975 current, 25 closed
as deleted, mean 1.21 versions per party. No overlaps, no gaps, never more than
one current version per key, no versions opened by an untracked change.

The design decision worth reading: the timeline is rebuilt per affected key
rather than appended to. The obvious incremental design closes the current row
and inserts a new one, which needs the union pattern because MERGE permits one
action per source row. It is also correct only while records arrive in order.
Defect 3 plants a record predating a version already loaded, and placing it
means rewriting the neighbouring rows on both sides, which MERGE cannot do in
one pass. Skipping such records would pass a naive test and fail convergence.
Rebuilding is idempotent by construction and converges under any replay order,
proven by an identical fingerprint after replaying 3, 1, 2.

Three failures worth keeping:

- A defect collision. Only 23 of the 25 planted deletions were happening,
  because the deleted set overlapped the parties carrying defects 2 and 3,
  whose extra rows bypass the snapshot filter. Those parties were deleted and
  still emitting versions, which is a contradictory state that no test caught
  because each defect was tested alone. The sets are disjoint now. Seeded
  defects have to be independent or they stop testing what they claim to.
- Literal control bytes in source. The change fingerprint uses a unit separator
  and a null marker, correctly: without a separator `("ab", "c")` and
  `("a", "bc")` fingerprint identically and a real change goes undetected. They
  were written as literal bytes rather than escapes, which makes the file fail
  with `source code string cannot contain null bytes`. Neither ruff nor
  `grep -P '\x00'` flagged it.
- SQL comment escaping. Doubling a quote is ANSI but Spark's parser rejected
  `version''s validity`; backslash escaping is what it expects. Every column
  comment about a version's validity hit it.

2026-08-09: Correction, from review-06 C-01. The convergence proof above is
order-lucky. Replay order 3,1,2 ends on batch 2, whose close_vanished
re-closes the deleted parties; any order ending in batch 1 resurrects all 25
(reproduced: current 1,975 to 2,000). Deletion state does not survive a
timeline rebuild, because the rebuild reads attributes only. Convergence
holds for attribute versions and fails for closures until review-06 C-01
lands. The fingerprint comparison stands as a test of the former, not the
latter.

2026-08-09, later: C-01 landed. Deletion is now derived from the full
snapshot stream in bronze on every build and re-applied after every rebuild
(ADR 0010, superseding 0007's mechanism). Convergence re-proven in the order
that caught the defect: in-order 1,2,3 and killer-order 2,3,1 produce
identical fingerprints (5195305383334, 2,424 rows, 1,975 current), and the
direct repro, replaying batch 1 on top, now re-closes all 25 in the same run.
Eleven transformation unit tests run in the container via `make test-spark`,
including the empty-extract guard from M-02 and the trailing-absence
semantics; the host suite skips them by design, since the host carries no
pyspark. The fingerprint differs from the one recorded above because ADR
0008's sentinel landed between the two measurements; the comparison that
matters is within-run, in-order versus out-of-order, and those are equal.
