"""The generator's contract: reproducible, and defective on purpose.

Each seeded defect gets a test here. If a defect stops being planted, the
pipeline downstream stops being exercised by it, and the test that proves the
pipeline handles it would start passing for the wrong reason.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

import pytest

from lakehouse.generate import BATCH_DATES, Generator


@pytest.fixture(scope="module")
def raw(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("raw")
    Generator().write(out)
    return out


def read(raw: Path, batch: str, name: str) -> list[dict]:
    with (raw / batch / f"{name}.csv").open() as fh:
        return list(csv.DictReader(fh))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_produces_identical_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    Generator().write(a)
    Generator().write(b)

    for batch in BATCH_DATES:
        for name in ("party", "account", "transaction"):
            assert digest(a / batch / f"{name}.csv") == digest(b / batch / f"{name}.csv")


def test_defect_1_exact_duplicate_rows_in_every_source(raw):
    for batch in BATCH_DATES:
        for name in ("party", "account", "transaction"):
            rows = [tuple(sorted(r.items())) for r in read(raw, batch, name)]
            assert len(rows) > len(set(rows)), f"{batch}/{name} has no duplicate rows"


def test_defect_2_a_party_changes_address_twice_in_one_day(raw):
    rows = read(raw, BATCH_DATES[0], "party")
    per_party_day = Counter((r["party_id"], r["updated_at"][:10]) for r in rows)
    assert any(count >= 2 for count in per_party_day.values())

    pid = next(p for (p, _), c in per_party_day.items() if c >= 2)
    stamps = sorted({r["updated_at"] for r in rows if r["party_id"] == pid})
    # Two versions on the same date at different times: an effective range
    # grained to the day cannot represent this.
    assert len({s[:10] for s in stamps}) < len(stamps)


def test_defect_3_a_record_arrives_out_of_sequence(raw):
    rows = read(raw, BATCH_DATES[1], "party")
    assert any(r["updated_at"][:10] < BATCH_DATES[0] for r in rows)


def test_defect_4_batch_1_transactions_reference_accounts_that_arrive_later(raw):
    b1_accounts = {r["account_id"] for r in read(raw, BATCH_DATES[0], "account")}
    b1_txn_accounts = {r["account_id"] for r in read(raw, BATCH_DATES[0], "transaction")}
    b2_accounts = {r["account_id"] for r in read(raw, BATCH_DATES[1], "account")}

    orphans = b1_txn_accounts - b1_accounts
    assert orphans, "batch 1 has no orphan account references"
    assert orphans <= b2_accounts, "orphans never arrive, which is a different defect"


def test_defect_5_settlement_lags_the_event_by_up_to_five_days(raw):
    rows = read(raw, BATCH_DATES[0], "transaction")
    lags = {(r["posted_ts"][:10] != r["txn_ts"][:10]) for r in rows}
    assert True in lags, "nothing posts on a later day than it occurred"
    assert all(r["posted_ts"] >= r["txn_ts"] for r in rows), "settlement precedes the event"


def test_defect_6_nulls_in_risk_rating_and_merchant_category(raw):
    parties = read(raw, BATCH_DATES[0], "party")
    txns = read(raw, BATCH_DATES[0], "transaction")

    assert any(r["risk_rating"] == "" for r in parties)
    assert any(r["merchant_category"] == "" for r in txns)


def test_defect_7_parties_are_hard_deleted_between_batches(raw):
    b1 = {r["party_id"] for r in read(raw, BATCH_DATES[0], "party")}
    b2 = {r["party_id"] for r in read(raw, BATCH_DATES[1], "party")}

    deleted = b1 - b2
    assert deleted, "no party disappears between batches"
    # Absence is only meaningful because party extracts are full snapshots.
    assert len(b2) < len(b1)
