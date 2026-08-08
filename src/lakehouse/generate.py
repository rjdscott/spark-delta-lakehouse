"""Generate the retail banking source extracts, deterministically.

Three batch dates, three sources, written as CSV to `data/raw/<batch>/`.

Extract shapes differ on purpose, because they differ in real banks:

- **party and account are full snapshots.** Every batch contains every record
  the source system currently holds. This is what makes a hard delete
  detectable at all: a party that stops appearing has been deleted, and that
  is only knowable when absence is meaningful.
- **transaction is an incremental event stream.** Each batch carries only the
  transactions that occurred since the last one. Events are not restated.

The generator plants seven defects on purpose. They are documented in
`data/DEFECTS.md` with the pipeline behaviour each one exercises. A pipeline
that only ever sees clean data proves nothing.

Determinism matters more than realism here: the same seed must produce
byte-identical files, so that a test can assert on content hashes and a
reviewer can reproduce a bug. Every random draw goes through one seeded
generator, and every collection is iterated in sorted order.
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
N_ACCOUNTS = 3000
N_TRANSACTIONS_PER_BATCH = 17000

STATES = ("NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT")
SUBURBS = ("Newtown", "Fitzroy", "Fortitude Valley", "Fremantle", "Norwood", "Battery Point")
RISK_RATINGS = ("LOW", "MEDIUM", "HIGH")
SEGMENTS = ("RETAIL", "PREMIUM", "STUDENT", "SENIOR")
PRODUCTS = ("TRANSACTION", "SAVINGS", "TERM_DEPOSIT", "CREDIT_CARD", "HOME_LOAN")
STATUSES = ("OPEN", "DORMANT", "CLOSED")
MERCHANT_CATEGORIES = ("GROCERY", "FUEL", "UTILITIES", "DINING", "TRAVEL", "HEALTH", "ATM")
TXN_TYPES = ("DEBIT", "CREDIT", "FEE", "INTEREST")

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
        # Defect 4: accounts deliberately withheld from batch 1 while their
        # transactions are not. Populated by _build_universe, released in
        # batch 2.
        self.late_accounts: set[str] = set()
        # Defect 7: parties present in batch 1 and absent from batch 2 onward.
        self.deleted_parties: set[str] = set()

    # --- universe -------------------------------------------------------

    def _build_universe(self) -> None:
        for i in range(N_PARTIES):
            pid = f"P{i:06d}"
            self.parties[pid] = {
                "party_id": pid,
                "full_name": f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
                "address_line": f"{self.rng.randint(1, 400)} {self.rng.choice(SUBURBS)} Road",
                "suburb": self.rng.choice(SUBURBS),
                "state": self.rng.choice(STATES),
                "postcode": f"{self.rng.randint(2000, 7999)}",
                # Defect 6: risk_rating is nullable in the source. A pipeline
                # that assumes otherwise fails on the first batch.
                "risk_rating": self.rng.choice(RISK_RATINGS) if self.rng.random() > 0.04 else "",
                "segment": self.rng.choice(SEGMENTS),
                "updated_at": f"{BATCH_DATES[0]}T00:00:00",
            }

        party_ids = sorted(self.parties)
        for i in range(N_ACCOUNTS):
            aid = f"A{i:06d}"
            opened = _date(BATCH_DATES[0]) - dt.timedelta(days=self.rng.randint(30, 3650))
            status = self.rng.choices(STATUSES, weights=(80, 15, 5))[0]
            self.accounts[aid] = {
                "account_id": aid,
                "party_id": self.rng.choice(party_ids),
                "product_type": self.rng.choice(PRODUCTS),
                "open_date": opened.isoformat(),
                "close_date": (
                    (opened + dt.timedelta(days=self.rng.randint(60, 2000))).isoformat()
                    if status == "CLOSED"
                    else ""
                ),
                "status": status,
                "updated_at": f"{BATCH_DATES[0]}T00:00:00",
            }

        account_ids = sorted(self.accounts)
        self.late_accounts = set(account_ids[-40:])
        self.deleted_parties = set(party_ids[:25])

    # --- per batch mutation ---------------------------------------------

    def _age_parties(self, batch: str) -> list[dict]:
        """Apply this batch's changes and return the full snapshot."""
        day = _date(batch)

        for pid in sorted(self.parties):
            if self.rng.random() < 0.10:
                p = self.parties[pid]
                p["address_line"] = f"{self.rng.randint(1, 400)} {self.rng.choice(SUBURBS)} Road"
                p["suburb"] = self.rng.choice(SUBURBS)
                p["updated_at"] = f"{batch}T09:00:00"

        ordered = sorted(self.parties)

        # Defect 2: one party changes address twice within the same day. SCD2
        # effective ranges therefore cannot be date-grained, and both versions
        # must survive.
        twice = self.parties[ordered[7]]
        twice["address_line"] = f"{self.rng.randint(1, 400)} Same Day Street"
        twice["updated_at"] = f"{batch}T11:15:00"
        rows = [dict(twice)]
        twice["address_line"] = f"{self.rng.randint(1, 400)} Same Day Terrace"
        twice["updated_at"] = f"{batch}T16:45:00"

        # Defect 3: a record whose updated_at predates a version already
        # loaded. Sequencing by updated_at must not let it overwrite newer
        # state.
        stale = dict(self.parties[ordered[11]])
        stale["segment"] = "STUDENT"
        stale["updated_at"] = f"{(day - dt.timedelta(days=45)).isoformat()}T08:00:00"
        rows.append(stale)

        snapshot = [
            dict(self.parties[pid])
            for pid in ordered
            # Defect 7: hard deletes. Present in batch 1, gone afterwards.
            if not (batch != BATCH_DATES[0] and pid in self.deleted_parties)
        ]
        return snapshot + rows

    def _age_accounts(self, batch: str) -> list[dict]:
        for aid in sorted(self.accounts):
            if self.rng.random() < 0.06:
                a = self.accounts[aid]
                a["status"] = self.rng.choice(STATUSES)
                if a["status"] == "CLOSED" and not a["close_date"]:
                    a["close_date"] = batch
                a["updated_at"] = f"{batch}T09:00:00"

        return [
            dict(self.accounts[aid])
            for aid in sorted(self.accounts)
            # Defect 4: these accounts exist upstream but are not released
            # until batch 2, while batch 1 already carries their transactions.
            if not (batch == BATCH_DATES[0] and aid in self.late_accounts)
        ]

    def _transactions(self, batch: str, index: int) -> list[dict]:
        day = _date(batch)
        account_ids = sorted(self.accounts)
        rows = []
        for i in range(N_TRANSACTIONS_PER_BATCH):
            # Batch 1 references the late accounts on purpose, so gold has
            # orphan references to resolve as inferred members.
            if index == 0 and i % 500 == 0:
                aid = sorted(self.late_accounts)[(i // 500) % len(self.late_accounts)]
            else:
                aid = self.rng.choice(account_ids)

            txn_ts = dt.datetime.combine(day, dt.time.min) - dt.timedelta(
                days=self.rng.randint(0, 29),
                seconds=self.rng.randint(0, 86399),
            )
            # Defect 5: settlement lags the event by up to five days, so a
            # transaction can post into a later batch than it occurred in.
            posted_ts = txn_ts + dt.timedelta(
                days=self.rng.choices((0, 1, 2, 5), weights=(70, 15, 10, 5))[0],
                seconds=self.rng.randint(0, 3600),
            )
            rows.append(
                {
                    "txn_id": f"T{index:02d}{i:08d}",
                    "account_id": aid,
                    "txn_ts": txn_ts.isoformat(sep=" ", timespec="seconds"),
                    "posted_ts": posted_ts.isoformat(sep=" ", timespec="seconds"),
                    "amount": f"{self.rng.uniform(-2500, 2500):.2f}",
                    "currency": "AUD",
                    # Defect 6, second column.
                    "merchant_category": (
                        self.rng.choice(MERCHANT_CATEGORIES) if self.rng.random() > 0.03 else ""
                    ),
                    "txn_type": self.rng.choice(TXN_TYPES),
                }
            )
        return rows

    # --- output ---------------------------------------------------------

    def _duplicate_some(self, rows: list[dict]) -> list[dict]:
        """Defect 1: exact duplicate rows, in every source, in every batch.

        Deduplication on the business key is the first thing silver has to do,
        and it has to do it without a distinct() that would also collapse
        legitimate same-key versions.
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
