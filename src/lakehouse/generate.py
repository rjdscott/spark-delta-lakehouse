"""Generate the retail banking source extracts, deterministically.

Three batch dates, three sources, written as CSV to `data/raw/<batch>/`.

**Coherence over fidelity.** Nobody will check this data against real banking
statistics, and it would not help if they did. What people do notice is a
mortgage account buying groceries, a closed account still transacting, or a
balance chart that random-walks into deep negative territory. So every number
here has to make sense against the row next to it:

- Debits and fees are negative, credits and interest positive. Summing a
  column therefore means something.
- Every account opens with a deposit, so a running balance is a real
  cumulative sum rather than a walk from zero.
- Transactions only occur while an account is open, and their merchant
  categories fit the product: a home loan repays, a term deposit accrues
  interest, a transaction account buys petrol.
- Suburb, state and postcode agree, because a Fremantle address in the
  Northern Territory is the sort of thing a reviewer spots immediately.

Deliberately not simulated: interest accrual formulas, fraud patterns, foreign
exchange, fee schedules, and anything else that would add realism without
adding a modelling problem to solve.

Extract shapes differ on purpose, because they differ in real banks:

- **party and account are full snapshots.** Every batch contains every record
  the source currently holds, which is what makes a hard delete detectable:
  absence is only information when presence was guaranteed.
- **transaction is an incremental event stream.** Events are facts about a
  moment and are not restated.

The generator plants seven defects on purpose, documented in
`data/DEFECTS.md`. A pipeline that only ever sees clean data proves nothing.

Determinism matters more than realism: the same seed must produce
byte-identical files, so a test can assert on content hashes and a reviewer
can reproduce a bug from the seed alone.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
from pathlib import Path

SEED = 42
BATCH_DATES = ("2026-01-15", "2026-02-15", "2026-03-15")

N_PARTIES = 2000

# Geography that agrees with itself: suburb, state and postcode travel together
# rather than being drawn independently.
LOCALITIES = (
    ("Newtown", "NSW", 2042),
    ("Surry Hills", "NSW", 2010),
    ("Fitzroy", "VIC", 3065),
    ("Brunswick", "VIC", 3056),
    ("Fortitude Valley", "QLD", 4006),
    ("West End", "QLD", 4101),
    ("Fremantle", "WA", 6160),
    ("Subiaco", "WA", 6008),
    ("Norwood", "SA", 5067),
    ("Battery Point", "TAS", 7004),
    ("Braddon", "ACT", 2612),
    ("Nightcliff", "NT", 810),
)

RISK_RATINGS = ("LOW", "MEDIUM", "HIGH")
SEGMENTS = ("RETAIL", "PREMIUM", "STUDENT", "SENIOR")

# Monthly income by segment, which drives the salary credit and therefore the
# shape of every balance chart in the demo.
SEGMENT_INCOME = {
    "STUDENT": (900, 1800),
    "RETAIL": (3200, 6500),
    "PREMIUM": (8000, 22000),
    "SENIOR": (1800, 3800),
}

# What each product is for. This is the table that stops a home loan from
# buying petrol.
PRODUCT_PROFILE = {
    "TRANSACTION": {
        "opening": (400, 4000),
        "spend_per_month": (18, 45),
        "categories": ("GROCERY", "FUEL", "DINING", "ATM", "UTILITIES", "HEALTH"),
        "salary": True,
        "monthly_interest": False,
    },
    "SAVINGS": {
        "opening": (2000, 60000),
        "spend_per_month": (0, 2),
        "categories": ("ATM",),
        "salary": False,
        "monthly_interest": True,
    },
    "CREDIT_CARD": {
        "opening": (0, 0),
        "spend_per_month": (12, 38),
        "categories": ("GROCERY", "DINING", "TRAVEL", "HEALTH", "FUEL"),
        "salary": False,
        "monthly_interest": False,
    },
    "TERM_DEPOSIT": {
        "opening": (10000, 250000),
        "spend_per_month": (0, 0),
        "categories": (),
        "salary": False,
        "monthly_interest": True,
    },
    "HOME_LOAN": {
        "opening": (-850000, -220000),
        "spend_per_month": (0, 0),
        "categories": (),
        "salary": False,
        "monthly_interest": False,
    },
}

# Plausible ranges per merchant category, so "spend by category" is a chart
# somebody can read rather than uniform noise.
CATEGORY_AMOUNT = {
    "GROCERY": (12, 320),
    "FUEL": (35, 190),
    "DINING": (18, 260),
    "UTILITIES": (80, 640),
    "TRAVEL": (150, 3200),
    "HEALTH": (25, 900),
    "ATM": (20, 500),
}

# Sign convention. Without one, summing amount is meaningless and every
# business example built on it is nonsense.
NEGATIVE_TYPES = ("DEBIT", "FEE")

FIRST_NAMES = ("Alice", "Bao", "Carlos", "Dana", "Eitan", "Fatima", "Grace", "Hiro", "Ines", "Jai")
LAST_NAMES = ("Nguyen", "Smith", "Okafor", "Rossi", "Patel", "Kim", "Silva", "Muller", "Haddad")


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


class Generator:
    """Holds the seeded state so a run is reproducible end to end."""

    def __init__(self, seed: int = SEED) -> None:
        self.rng = random.Random(seed)
        self.parties: dict[str, dict] = {}
        self.accounts: dict[str, dict] = {}
        self.late_accounts: set[str] = set()
        self.deleted_parties: set[str] = set()
        self._txn_seq = 0

    # --- universe -------------------------------------------------------

    def _build_universe(self) -> None:
        first_batch = _date(BATCH_DATES[0])

        for i in range(N_PARTIES):
            pid = f"P{i:06d}"
            suburb, state, postcode = self.rng.choice(LOCALITIES)
            self.parties[pid] = {
                "party_id": pid,
                "full_name": f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
                "address_line": f"{self.rng.randint(1, 400)} {suburb} Road",
                "suburb": suburb,
                "state": state,
                "postcode": f"{postcode:04d}",
                # Defect 6: risk_rating is nullable at source.
                "risk_rating": self.rng.choice(RISK_RATINGS) if self.rng.random() > 0.04 else "",
                "segment": self.rng.choices(SEGMENTS, weights=(60, 15, 15, 10))[0],
                "updated_at": f"{BATCH_DATES[0]}T00:00:00",
            }

        # Most people hold one or two accounts, a few hold several. Drawing
        # accounts independently of parties produced customers with eight
        # accounts and customers with none.
        account_index = 0
        for pid in sorted(self.parties):
            for _ in range(self.rng.choices((1, 2, 3), weights=(55, 33, 12))[0]):
                aid = f"A{account_index:06d}"
                account_index += 1
                product = self.rng.choices(tuple(PRODUCT_PROFILE), weights=(45, 25, 18, 7, 5))[0]
                opened = first_batch - dt.timedelta(days=self.rng.randint(45, 3650))
                status = self.rng.choices(("OPEN", "DORMANT", "CLOSED"), weights=(84, 11, 5))[0]
                close_date = (
                    opened + dt.timedelta(days=self.rng.randint(60, 2000))
                    if status == "CLOSED"
                    else None
                )
                self.accounts[aid] = {
                    "account_id": aid,
                    "party_id": pid,
                    "product_type": product,
                    "open_date": opened.isoformat(),
                    "close_date": close_date.isoformat() if close_date else "",
                    "status": status,
                    "updated_at": f"{BATCH_DATES[0]}T00:00:00",
                }

        account_ids = sorted(self.accounts)
        self.late_accounts = set(account_ids[-40:])
        self.deleted_parties = set(sorted(self.parties)[:25])

    # --- per batch mutation ---------------------------------------------

    def _age_parties(self, batch: str) -> list[dict]:
        day = _date(batch)

        for pid in sorted(self.parties):
            if self.rng.random() < 0.10:
                p = self.parties[pid]
                suburb, state, postcode = self.rng.choice(LOCALITIES)
                p["address_line"] = f"{self.rng.randint(1, 400)} {suburb} Road"
                p["suburb"], p["state"], p["postcode"] = suburb, state, f"{postcode:04d}"
                p["updated_at"] = f"{batch}T09:00:00"

        ordered = sorted(self.parties)

        # Defect 2: one party changes address twice within the same day, so
        # SCD2 effective ranges cannot be date-grained.
        twice = self.parties[ordered[7]]
        suburb, state, postcode = self.rng.choice(LOCALITIES)
        twice["address_line"] = f"{self.rng.randint(1, 400)} {suburb} Street"
        twice["suburb"], twice["state"], twice["postcode"] = suburb, state, f"{postcode:04d}"
        twice["updated_at"] = f"{batch}T11:15:00"
        extra = [dict(twice)]
        suburb, state, postcode = self.rng.choice(LOCALITIES)
        twice["address_line"] = f"{self.rng.randint(1, 400)} {suburb} Terrace"
        twice["suburb"], twice["state"], twice["postcode"] = suburb, state, f"{postcode:04d}"
        twice["updated_at"] = f"{batch}T16:45:00"

        # Defect 3: a record whose updated_at predates a version already
        # loaded. Sequencing must not let it overwrite newer state.
        stale = dict(self.parties[ordered[11]])
        stale["segment"] = "STUDENT"
        stale["updated_at"] = f"{(day - dt.timedelta(days=45)).isoformat()}T08:00:00"
        extra.append(stale)

        snapshot = [
            dict(self.parties[pid])
            for pid in ordered
            # Defect 7: hard deletes, present in batch 1 and gone afterwards.
            if not (batch != BATCH_DATES[0] and pid in self.deleted_parties)
        ]
        return snapshot + extra

    def _age_accounts(self, batch: str) -> list[dict]:
        for aid in sorted(self.accounts):
            a = self.accounts[aid]
            # An account's status only ever moves forward. Reopening a closed
            # account would make the lifecycle fact incoherent.
            if a["status"] != "CLOSED" and self.rng.random() < 0.05:
                a["status"] = self.rng.choices(("DORMANT", "CLOSED"), weights=(70, 30))[0]
                if a["status"] == "CLOSED":
                    a["close_date"] = batch
                a["updated_at"] = f"{batch}T09:00:00"

        return [
            dict(self.accounts[aid])
            for aid in sorted(self.accounts)
            # Defect 4: these exist upstream but are withheld until batch 2,
            # while batch 1 already carries their transactions.
            if not (batch == BATCH_DATES[0] and aid in self.late_accounts)
        ]

    # --- transactions ----------------------------------------------------

    def _txn(self, account: dict, when: dt.datetime, txn_type: str, category: str, amount: float):
        self._txn_seq += 1
        # Defect 5: settlement lags the event by up to five days, so a
        # transaction can post into a later batch than it occurred in.
        posted = when + dt.timedelta(
            days=self.rng.choices((0, 1, 2, 5), weights=(70, 15, 10, 5))[0],
            seconds=self.rng.randint(0, 3600),
        )
        signed = -abs(amount) if txn_type in NEGATIVE_TYPES else abs(amount)
        return {
            "txn_id": f"T{self._txn_seq:010d}",
            "account_id": account["account_id"],
            "txn_ts": when.isoformat(sep=" ", timespec="seconds"),
            "posted_ts": posted.isoformat(sep=" ", timespec="seconds"),
            "amount": f"{signed:.2f}",
            "currency": "AUD",
            # Defect 6, second column.
            "merchant_category": ("" if category and self.rng.random() < 0.03 else category),
            "txn_type": txn_type,
        }

    def _active(self, account: dict, day: dt.date) -> bool:
        """An account transacts only while it is open. A closed account still
        producing activity is the first thing a reviewer notices."""
        if _date(account["open_date"]) > day:
            return False
        if account["close_date"] and _date(account["close_date"]) <= day:
            return False
        return account["status"] != "DORMANT"

    def _transactions(self, batch: str, index: int) -> list[dict]:
        period_end = _date(batch)
        period_start = period_end - dt.timedelta(days=30)
        rows: list[dict] = []

        for aid in sorted(self.accounts):
            account = self.accounts[aid]
            profile = PRODUCT_PROFILE[account["product_type"]]
            party = self.parties[account["party_id"]]

            def moment() -> dt.datetime:
                return dt.datetime.combine(period_start, dt.time.min) + dt.timedelta(
                    days=self.rng.randint(0, 29), seconds=self.rng.randint(0, 86399)
                )

            # The opening deposit, once, so a running balance is a real
            # cumulative sum rather than a walk from zero.
            if index == 0:
                low, high = profile["opening"]
                if low or high:
                    opening = self.rng.uniform(low, high)
                    rows.append(
                        self._txn(
                            account,
                            dt.datetime.combine(period_start, dt.time(0, 5)),
                            "CREDIT" if opening >= 0 else "DEBIT",
                            "",
                            opening,
                        )
                    )

            if not self._active(account, period_end):
                continue

            if profile["salary"]:
                low, high = SEGMENT_INCOME[party["segment"]]
                rows.append(self._txn(account, moment(), "CREDIT", "", self.rng.uniform(low, high)))

            if profile["monthly_interest"]:
                rows.append(self._txn(account, moment(), "INTEREST", "", self.rng.uniform(2, 240)))

            if account["product_type"] == "HOME_LOAN":
                rows.append(self._txn(account, moment(), "DEBIT", "", self.rng.uniform(1400, 4800)))

            if account["product_type"] == "CREDIT_CARD" and self.rng.random() < 0.8:
                rows.append(self._txn(account, moment(), "CREDIT", "", self.rng.uniform(200, 4000)))

            low, high = profile["spend_per_month"]
            for _ in range(self.rng.randint(low, high) if high else 0):
                category = self.rng.choice(profile["categories"])
                amount_low, amount_high = CATEGORY_AMOUNT[category]
                rows.append(
                    self._txn(
                        account,
                        moment(),
                        "DEBIT",
                        category,
                        self.rng.uniform(amount_low, amount_high),
                    )
                )

            if self.rng.random() < 0.15:
                rows.append(self._txn(account, moment(), "FEE", "", self.rng.uniform(2, 35)))

        return rows

    # --- output ---------------------------------------------------------

    def _duplicate_some(self, rows: list[dict]) -> list[dict]:
        """Defect 1: exact duplicate rows, every source, every batch.

        Deduplication on the business key is the first thing silver does, and
        it cannot be a DISTINCT: that would also collapse the two legitimate
        same-day party versions from defect 2.
        """
        if not rows:
            return rows
        picks = sorted(self.rng.sample(range(len(rows)), k=max(1, len(rows) // 200)))
        return rows + [dict(rows[i]) for i in picks]

    def write(self, out: Path) -> dict[str, int]:
        self._build_universe()
        counts: dict[str, int] = {}
        for index, batch in enumerate(BATCH_DATES):
            target = out / batch
            target.mkdir(parents=True, exist_ok=True)
            for name, rows in (
                ("party", self._age_parties(batch)),
                ("account", self._age_accounts(batch)),
                ("transaction", self._transactions(batch, index)),
            ):
                rows = self._duplicate_some(rows)
                path = target / f"{name}.csv"
                with path.open("w", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                counts[f"{batch}/{name}"] = len(rows)
        return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)

    counts = Generator(args.seed).write(args.out)
    for key in sorted(counts):
        print(f"{key:40s} {counts[key]:>7,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
