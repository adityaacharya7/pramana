"""Shared building blocks for the synthetic dataset: identifier generation,
bank-statement construction and file writing.

Everything here is invented. Identifiers are drawn from a seeded RNG so a
given seed always produces byte-identical files (the manifest hashes depend
on it).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

PERIOD_START = datetime(2026, 7, 1, 0, 0, 0)
PERIOD_END = datetime(2026, 8, 31, 23, 59, 59)

BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Fictional banks. The "Synthetic/Demo/Test/Sample/Fixture" names are
# deliberate: nothing in this dataset should be mistaken for a real institution.
BANKS = {
    "XSSB": "Sahyadri Synthetic Bank",
    "XNDB": "Narmada Demo Bank",
    "XKTB": "Kaveri Test Bank",
    "XGSB": "Ganga Sample Bank",
    "XYFB": "Yamuna Fixture Bank",
}

STATEMENT_COLUMNS = [
    "account_no", "txn_time", "txn_id", "reference", "description", "channel",
    "counterparty_account", "counterparty_name", "debit", "credit", "balance",
]


def luhn_digit(digits: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


class IdGen:
    """Unique, seeded identifiers. Every value handed out is remembered so two
    unrelated entities never collide by accident; intentional sharing (the
    point of the dataset) is done by reusing the returned value."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set[str] = set()

    def _unique(self, make) -> str:
        for _ in range(10_000):
            value = make()
            if value not in self.used:
                self.used.add(value)
                return value
        raise RuntimeError("identifier space exhausted")

    def phone(self) -> str:
        return self._unique(
            lambda: self.rng.choice("6789") + "".join(self.rng.choice("0123456789") for _ in range(9))
        )

    def account(self, length: int | None = None) -> str:
        n = length or self.rng.choice([11, 12, 13, 14])
        return self._unique(
            lambda: self.rng.choice("123456789") + "".join(self.rng.choice("0123456789") for _ in range(n - 1))
        )

    def reference(self) -> str:
        # IMPS RRN-style 12-digit reference. Both sides of one transfer carry
        # the same reference, which is what lets two statements be recognised
        # as two views of one underlying bank record.
        return self._unique(lambda: "62" + "".join(self.rng.choice("0123456789") for _ in range(10)))

    def txn_id(self, bank_code: str) -> str:
        return self._unique(
            lambda: bank_code[1:] + "".join(self.rng.choice("0123456789") for _ in range(9))
        )

    def imei(self) -> str:
        def make():
            body = "35" + "".join(self.rng.choice("0123456789") for _ in range(12))
            return body + luhn_digit(body)
        return self._unique(make)

    def imsi(self) -> str:
        return self._unique(lambda: "40410" + "".join(self.rng.choice("0123456789") for _ in range(10)))

    def tron_wallet(self) -> str:
        return self._unique(lambda: "T" + "".join(self.rng.choice(BASE58) for _ in range(33)))

    def sha256_token(self) -> str:
        return self._unique(lambda: "%064x" % self.rng.getrandbits(256))

    def device_id(self) -> str:
        return self._unique(lambda: "DEV-" + "".join(self.rng.choice("0123456789ABCDEF") for _ in range(12)))

    def masked_aadhaar(self) -> str:
        return self._unique(lambda: "XXXX-XXXX-" + "".join(self.rng.choice("0123456789") for _ in range(4)))

    def upi(self, handle: str) -> str:
        suffix = self.rng.choice(["synupi", "fakepay", "demobank"])
        return self._unique(lambda: f"{handle}{self.rng.randint(10, 99)}@{suffix}")


def fmt_inr(amount: float) -> str:
    """Indian digit grouping: 160000 -> '1,60,000'."""
    whole = int(round(amount))
    s = str(whole)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


@dataclass
class Txn:
    time: datetime
    description: str
    channel: str
    counterparty_account: str
    counterparty_name: str
    debit: float = 0.0
    credit: float = 0.0
    reference: str = ""
    tag: str = ""  # generator-side label (never written to the CSV)


@dataclass
class Statement:
    account_no: str
    bank_code: str
    holder: str
    opening: float
    txns: list[Txn] = field(default_factory=list)
    start: datetime = PERIOD_START
    end: datetime = PERIOD_END
    date_style: str = "iso"  # "iso" or "dmy" (planted ambiguity)
    drop_row_index: int | None = None  # planted non-reconciling statement

    def add(self, txn: Txn) -> Txn:
        self.txns.append(txn)
        return txn

    def sorted_txns(self) -> list[Txn]:
        return sorted(self.txns, key=lambda t: t.time)

    def closing(self) -> float:
        bal = self.opening
        for t in self.sorted_txns():
            bal += t.credit - t.debit
        return round(bal, 2)

    def min_balance(self) -> float:
        bal, low = self.opening, self.opening
        for t in self.sorted_txns():
            bal += t.credit - t.debit
            low = min(low, bal)
        return low

    def _fmt_time(self, t: datetime) -> str:
        if self.date_style == "dmy":
            return t.strftime("%d/%m/%Y %H:%M")
        return t.strftime("%Y-%m-%d %H:%M:%S")

    def to_csv(self, ids: IdGen) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(STATEMENT_COLUMNS)
        w.writerow([self.account_no, self._fmt_time(self.start), "", "", "OPENING BALANCE", "",
                    "", "", "", "", f"{self.opening:.2f}"])
        bal = self.opening
        for i, t in enumerate(self.sorted_txns()):
            bal = round(bal + t.credit - t.debit, 2)
            if i == self.drop_row_index:
                # The balance column keeps moving, so the omission is only
                # visible when opening + credits - debits is reconciled.
                continue
            w.writerow([
                self.account_no, self._fmt_time(t.time), ids.txn_id(self.bank_code), t.reference,
                t.description, t.channel, t.counterparty_account, t.counterparty_name,
                f"{t.debit:.2f}" if t.debit else "", f"{t.credit:.2f}" if t.credit else "",
                f"{bal:.2f}",
            ])
        w.writerow([self.account_no, self._fmt_time(self.end), "", "", "CLOSING BALANCE", "",
                    "", "", "", "", f"{bal:.2f}"])
        return buf.getvalue()


def rows_to_csv(columns: list[str], rows: Iterable[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DatasetWriter:
    """Writes files and records each one for the manifest."""

    def __init__(self, root: Path):
        self.root = root
        self.files: list[dict] = []

    def write(self, rel_path: str, text: str, *, case_id: str | None, kind: str,
              language: str = "en", live_upload: bool = False, note: str = "") -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        path.write_bytes(data)
        entry = {
            "path": rel_path.replace("\\", "/"),
            "case_id": case_id,
            "kind": kind,
            "language": language,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
        }
        if live_upload:
            entry["demo_live_upload"] = True
        if note:
            entry["note"] = note
        self.files.append(entry)
        return rel_path

    def write_json(self, rel_path: str, obj) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def at(day: int, hh: int, mm: int, month: int = 8, ss: int = 0) -> datetime:
    return datetime(2026, month, day, hh, mm, ss)


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)
