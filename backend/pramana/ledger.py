"""Tamper-evident audit log: an append-only hash chain.

    h_n = SHA256( h_{n-1} | n | t_n | actor_n | action_n | SHA256(payload_n) )

Fields are joined with the ASCII unit separator (0x1F) so the concatenation
is unambiguous, and the payload is canonical JSON. The genesis entry chains
from 64 zeros.

What this does and does not prove (spec, "Security, integrity and ledger"):
on its own a centralised chain catches careless edits, deletions and
reordering. Someone who can rewrite the database can recompute every later
hash, so a fully rewritten chain still verifies. That gap is closed by signed
checkpoints retained outside the database (F14, week 5); until then
``verify`` says so in its report instead of implying more.

Writers use ``transaction()`` so the audited change and its ledger entry
commit together, and appends are serialised (process lock, plus a database
advisory lock on PostgreSQL so separate instances cannot race).
"""
from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import utcnow_iso
from .models import LedgerEntry

GENESIS = "0" * 64
SEP = "\x1f"
_LOCK = threading.RLock()


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry_hash(prev_hash: str, seq: int, ts: str, actor: str, action: str, payload_hash: str) -> str:
    return sha256_hex(SEP.join([prev_hash, str(seq), ts, actor, action, payload_hash]))


LEDGER_LOCK_KEY = 0x50524D4E  # "PRMN"


@contextmanager
def transaction(session: Session) -> Iterator[None]:
    """Commit the caller's changes and their ledger entries atomically, with
    appends serialised so sequence numbers never race.

    Within one process a lock serialises writers. On PostgreSQL a
    transaction-scoped advisory lock does the same across processes and
    serverless instances; it is released by the commit or rollback."""
    with _LOCK:
        try:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LEDGER_LOCK_KEY})
            yield
            session.commit()
        except Exception:
            session.rollback()
            raise


def append(session: Session, *, actor: str, action: str, payload: dict[str, Any] | None = None) -> LedgerEntry:
    """Add an entry to the session. Call inside ``transaction()``."""
    if not _LOCK._is_owned():  # type: ignore[attr-defined]
        raise RuntimeError("ledger.append must be called inside ledger.transaction()")
    payload = dict(payload or {})
    body = canonical(payload)
    last = session.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    seq = (last.seq + 1) if last else 1
    prev = last.hash if last else GENESIS
    ts = utcnow_iso()
    p_hash = sha256_hex(body)
    entry = LedgerEntry(
        seq=seq, ts=ts, actor=actor, action=action, payload=body,
        case_id=payload.get("case_id"), payload_hash=p_hash, prev_hash=prev,
        hash=entry_hash(prev, seq, ts, actor, action, p_hash),
    )
    session.add(entry)
    session.flush()
    return entry


def record(session: Session, *, actor: str, action: str, payload: dict[str, Any] | None = None) -> LedgerEntry:
    """Append and commit a standalone entry (e.g. a refused access attempt,
    which must be logged even though the request itself fails)."""
    with transaction(session):
        return append(session, actor=actor, action=action, payload=payload)


def verify(session: Session) -> dict[str, Any]:
    entries = session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq)).all()
    prev = GENESIS
    expected_seq = 1
    for e in entries:
        problem = None
        if e.seq != expected_seq:
            problem = f"sequence gap: expected {expected_seq}, found {e.seq} (entry deleted or reordered)"
        elif e.prev_hash != prev:
            problem = "previous-hash link broken"
        elif sha256_hex(e.payload) != e.payload_hash:
            problem = "payload does not match its hash (payload edited)"
        elif entry_hash(e.prev_hash, e.seq, e.ts, e.actor, e.action, e.payload_hash) != e.hash:
            problem = "entry hash does not match its fields (entry edited)"
        else:
            try:
                in_payload = json.loads(e.payload).get("case_id")
            except ValueError:
                in_payload = object()
            if in_payload != e.case_id:
                problem = "case reference differs from the hashed payload"
        if problem:
            return {
                "ok": False, "entries": len(entries), "first_bad_seq": e.seq, "reason": problem,
                "head_seq": entries[-1].seq if entries else 0, "head_hash": entries[-1].hash if entries else GENESIS,
                **_coverage(),
            }
        prev = e.hash
        expected_seq += 1
    return {
        "ok": True, "entries": len(entries), "first_bad_seq": None, "reason": None,
        "head_seq": entries[-1].seq if entries else 0, "head_hash": prev, **_coverage(),
    }


def _coverage() -> dict[str, Any]:
    return {
        "checked_against": "internal chain only",
        "latest_trusted_checkpoint": None,
        "limitation": "No signed checkpoint is retained yet, so a chain rewritten with recomputed hashes would "
                      "still verify. Signed checkpoints kept outside the database close this (planned, F14).",
    }
