"""The generator's contract: reproducible, and defective on purpose.

Each seeded defect gets a test here. If a defect stops being planted, the
pipeline downstream stops being exercised by it, and the test that proves the
pipeline handles it would start passing for the wrong reason.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
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
    """Two *distinct* timestamps on one date.

    Counting rows per (party, date) is not enough: defect 1 plants exact
    duplicates, so a duplicated party has two rows on one date without having
    changed at all. Ten of the eleven candidates in batch 1 are duplicates,
    and an earlier version of this test passed only because the real one
    happened to sort first.
    """
    rows = read(raw, BATCH_DATES[0], "party")

    stamps_by_party: dict[str, set[str]] = {}
    for r in rows:
        stamps_by_party.setdefault(r["party_id"], set()).add(r["updated_at"])

    same_day = {
        pid: stamps
        for pid, stamps in stamps_by_party.items()
        if len(stamps) > 1 and len({s[:10] for s in stamps}) < len(stamps)
    }
    assert same_day, "no party has two distinct timestamps on one date"

    # An effective range grained to the day cannot represent this, which is
    # the whole reason SCD2 here is timestamp-grained.
    pid, stamps = sorted(same_day.items())[0]
    addresses = {r["address_line"] for r in rows if r["party_id"] == pid}
    assert len(addresses) > 1, f"{pid} has two timestamps but one address"


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

    lags = [
        dt.datetime.fromisoformat(r["posted_ts"]) - dt.datetime.fromisoformat(r["txn_ts"])
        for r in rows
    ]

    assert any(lag.days >= 1 for lag in lags), "nothing posts later than it occurred"
    assert min(lags) >= dt.timedelta(0), "settlement precedes the event"
    # The bound is in the name, so it belongs in the assertion. Without it a
    # fifty-day lag would pass.
    assert max(lags) <= dt.timedelta(days=5, hours=1), f"lag exceeds five days: {max(lags)}"


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


def test_amount_sign_agrees_with_transaction_type(raw):
    """Without a sign convention, summing amount is meaningless and every
    business example built on it is nonsense."""
    for batch in BATCH_DATES:
        for r in read(raw, batch, "transaction"):
            amount = float(r["amount"])
            if r["txn_type"] in ("DEBIT", "FEE"):
                assert amount <= 0, f"{r['txn_id']} is a {r['txn_type']} of {amount}"
            else:
                assert amount >= 0, f"{r['txn_id']} is a {r['txn_type']} of {amount}"


def test_merchant_categories_fit_the_product(raw):
    """A home loan does not buy groceries."""
    accounts = {r["account_id"]: r for r in read(raw, BATCH_DATES[2], "account")}
    seen: dict[str, set[str]] = {}
    for r in read(raw, BATCH_DATES[2], "transaction"):
        account = accounts.get(r["account_id"])
        if account and r["merchant_category"]:
            seen.setdefault(account["product_type"], set()).add(r["merchant_category"])

    assert "HOME_LOAN" not in seen
    assert "TERM_DEPOSIT" not in seen
    assert seen["SAVINGS"] == {"ATM"}
    assert "TRAVEL" not in seen["TRANSACTION"]


def test_no_transactions_after_an_account_closes(raw):
    """A closed account still transacting is the first thing a reviewer
    notices, and it would corrupt the accumulating snapshot in gold.

    Checked across every batch. An earlier version of this test read only the
    last one and passed while 87 violations sat in batch 1.
    """
    for batch in BATCH_DATES:
        accounts = {r["account_id"]: r for r in read(raw, batch, "account")}
        for r in read(raw, batch, "transaction"):
            account = accounts.get(r["account_id"])
            if account and account["close_date"]:
                assert r["txn_ts"][:10] < account["close_date"], (
                    f"{r['txn_id']} on {r['account_id']} closed {account['close_date']}"
                )


def test_geography_is_internally_consistent(raw):
    """Suburb, state and postcode travel together or the address is fiction."""
    pairs = {(r["suburb"], r["state"], r["postcode"]) for r in read(raw, BATCH_DATES[0], "party")}
    by_suburb: dict[str, set] = {}
    for suburb, state, postcode in pairs:
        by_suburb.setdefault(suburb, set()).add((state, postcode))
    for suburb, values in by_suburb.items():
        assert len(values) == 1, f"{suburb} appears in {values}"


def balances_by_product(raw) -> dict[str, list[float]]:
    accounts = {r["account_id"]: r for r in read(raw, BATCH_DATES[2], "account")}
    running: dict[str, float] = {}
    for batch in BATCH_DATES:
        for r in read(raw, batch, "transaction"):
            running[r["account_id"]] = running.get(r["account_id"], 0.0) + float(r["amount"])

    out: dict[str, list[float]] = {}
    for account_id, balance in running.items():
        if account_id in accounts:
            out.setdefault(accounts[account_id]["product_type"], []).append(balance)
    return out


def median(values: list[float]) -> float:
    return sorted(values)[len(values) // 2]


# The balance rule was the only coherence rule in data/DEFECTS.md without a
# test, and it was the rule that broke: credit cards reached a median of
# -32,589 before this existed. Ranges are deliberately wide. This is a
# plausibility guard, not a distribution assertion.
PLAUSIBLE_MEDIAN = {
    "TRANSACTION": (0, 40_000),
    "SAVINGS": (500, 150_000),
    "TERM_DEPOSIT": (5_000, 400_000),
    "CREDIT_CARD": (-20_000, 2_000),
    "HOME_LOAN": (-1_200_000, -50_000),
}


@pytest.mark.parametrize("product", sorted(PLAUSIBLE_MEDIAN))
def test_balances_are_plausible_for_the_product(raw, product):
    balances = balances_by_product(raw)[product]
    low, high = PLAUSIBLE_MEDIAN[product]

    assert low <= median(balances) <= high, (
        f"{product} median balance {median(balances):,.0f} outside [{low:,}, {high:,}]"
    )


def test_a_dormant_account_is_quiet_not_dead(raw):
    """Status is current state; transactions are history. Gating January's
    activity on a status reached in March erases the past."""
    accounts = {r["account_id"]: r for r in read(raw, BATCH_DATES[2], "account")}
    dormant = {a for a, r in accounts.items() if r["status"] == "DORMANT"}
    active = {r["account_id"] for batch in BATCH_DATES for r in read(raw, batch, "transaction")}

    assert dormant, "no dormant accounts to check"
    assert dormant <= active, "a dormant account has no history at all"
