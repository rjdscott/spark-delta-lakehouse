# Review-07 punchlist

Two axes: severity (from the findings) and priority (P0 fix before the next
demo, P1 before showing this to anyone skeptical, P2 soon, P3 nice to have).
Remediation PRs cite the finding codes.

## P0: the demo shows wrong numbers or dies on a fresh machine

- [x] **H-01** P0: widen `build_dim_date` to cover account open/close dates;
      extend the orphan check to `fact_account_lifecycle` and
      `fact_daily_balance`
- [x] **H-02** P0: clamp the generator's initial close_date draw to the
      first batch date; regenerate data; pin the invariant in
      test_generate and verify_gold
- [x] **H-03** P0: classify blank-category debits on merchant-less products
      as NOT_APPLICABLE, not UNKNOWN
- [x] **H-04** P0: fix the effective_to catalog comment ("9999-12-31 while
      current"); propagate to the live tables
- [x] **H-16** P0: reorder the bronze rescue projection so the branch works;
      plant an eighth defect exercising it; add a read_extract test
- [x] **H-21** P0: create the UC namespace in compose (`uc-init` service),
      so a cold stack matches the README's claim
- [x] **H-30** P0: refresh the phase-07/08 Verification fences to current
      output; annotate review-05 M-05 as partially applied

## P1: the correctness claims a skeptic will probe

- [ ] **H-09** P1: decide the fix for order-dependent no-op version loss:
      source `existing` from bronze (needs an ADR) or retract the universal
      convergence claim and add the counterexample test. Do not leave the
      claim as written
- [ ] **M-10** P1: proportional mass-deletion guard; assert the zero-current
      count in verify_scd2 instead of printing it
- [ ] **M-11** P1: apply_deletions count under the MERGE's own predicate;
      first test for the function
- [ ] **M-12** P1: decide untracked-attribute semantics (type 1 vs frozen);
      pin with a test either way
- [ ] **M-05** P1: replace verify_gold's tautological balance checks with
      gold-to-silver reconciliation
- [ ] **M-17** P1: bronze header-vs-spec check so a dropped source column
      raises instead of shifting values
- [ ] **M-18** P1: point the determinism test at the committed data/raw
      digests
- [ ] **M-22** P1: fix the runbook service count; make stack-ps show exited
      init containers or gate on minio-init in compose
- [ ] **M-28** P1: correct CLAUDE.md's branch-protection sentence
- [ ] **M-34** P1: correct CLAUDE.md's requirements-dev.txt and phasing
      lines

## P2: drift traps and unrecorded decisions

- [ ] **M-07** P2: drive the orphan-key loop from spec.relationships;
      correct the generated bus-matrix wording
- [ ] **M-06** P2: column comments for the OPENING measure rule in
      gold_fact_daily_balance.yml
- [ ] **M-08** P2: add the as-of vs current side-by-side query (spend by
      state) to demo_queries
- [ ] **M-13** P2: fix or make true upsert_scd1's defect-3 attribution
- [ ] **M-23** P2: drop bronze.smoke in reset.py
- [ ] **M-24** P2: thread HIVE_IMAGE through the Spark build; define
      HIVE_IMAGE_TAG
- [ ] **M-25** P2: correct .env's credential inventory or template
      server.properties
- [ ] **M-26** P2: document the memory/disk floor and the knobs
- [ ] **M-27** P2: delete or activate the dead pyproject COPY
- [ ] **M-31** P2: dated amendment note recording the departure from the
      brief
- [ ] **M-32** P2: ADRs for surrogate key strategy and SCD type per entity;
      below-the-bar notes for the rest
- [ ] **M-33** P2: layer-flow and SCD2-timeline diagrams, or record the
      drop; state the pre-commit decision

## P3: polish

- [ ] **L-09** P3: anchor days_open to the warehouse high-water mark
- [ ] **L-14** P3: scd2 dedupe tiebreak over all attributes
- [x] **L-15** P3: scd2 docstring defect count and deletion paragraph
      (done alongside the P0s: the defect-8 addition made the stale count
      actively false, so it was corrected in the same pass)
- [ ] **L-19** P3: DEFECTS.md forty-vs-37 wording; pin the count
- [ ] **L-20** P3: defect-6 realised percentages with denominators
- [ ] **L-29** P3: .dockerignore
- [ ] **L-35** P3: ADR pointer corrections in config and verify output

## Cross-ticks to prior reviews

- [x] review-05 todo: annotate M-05 as partially applied (H-30)
- [x] review-05 todo: M-06 closed, `make help` covers all targets
- [x] review-04 todo: M-04 closed as resolved-by-behavior (106
      no-transaction accounts, all pre-window closures)
