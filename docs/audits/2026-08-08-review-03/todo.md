# Punchlist: review-03

Severity `<C|H|M|L>-NN`, priority P0 before silver is built on top / P1 before
the demo / P2 soon / P3 nice.

- [ ] **H-01** P0: select the same-day change on distinct timestamps, not row
  count, so duplicates cannot satisfy the test.
  [`01-code-and-model.md#h-01`](01-code-and-model.md#h-01)
- [ ] **H-02** P0: bronze attributes become `string`. Coercion is silver's job
  and rescued data depends on it. [`#h-02`](01-code-and-model.md#h-02)
- [ ] **H-03** P0: bring the spec conformance test forward to phase 05, where
  the first tables are created. [`#h-03`](01-code-and-model.md#h-03)
- [ ] **M-04** P1: sign convention and opening balances in the generator, or
  every business example is nonsense. [`#m-04`](01-code-and-model.md#m-04)
- [ ] **M-05** P1: make the package installable; delete three PYTHONPATH
  workarounds. [`#m-05`](01-code-and-model.md#m-05)
- [ ] **M-06** P1: split `source` into `source_file` and `source_spec`.
  [`#m-06`](01-code-and-model.md#m-06)
- [ ] **M-07** P2: one source for the MinIO credentials; split version pins
  from secrets in `docker/.env`. [`#m-07`](01-code-and-model.md#m-07)
- [ ] **M-08** P2: assert the five-day bound the test claims to check.
  [`#m-08`](01-code-and-model.md#m-08)
- [ ] **L-09** P3: use the public status tracker in the smoke test.
  [`#l-09`](01-code-and-model.md#l-09)
- [ ] **L-10** P3: drop the redundant tuple re-packing and the `field` import.
  [`#l-10`](01-code-and-model.md#l-10)
- [ ] **L-11** P2: state in the README what CI does and does not cover.
  [`#l-11`](01-code-and-model.md#l-11)

## Deliberately not doing

- **Running the stack in CI.** GitHub runners can host Docker, but a Spark
  cluster plus MinIO plus two Postgres instances per PR is a long build for a
  repo whose pipeline logic is better tested at the unit level. Revisit if the
  stack breaks twice without anyone noticing.
