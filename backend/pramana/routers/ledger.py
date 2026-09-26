from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ledger
from ..deps import current_user, get_db
from ..models import LedgerEntry, User
from ..permissions import ANY, require_action, visible_case_ids
from ..schemas import LedgerEntryOut

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/verify")
def verify_ledger(user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_action(db, user, "ledger.verify")
    report = ledger.verify(db)
    ledger.record(db, actor=user.username, action="LEDGER_VERIFIED", payload={
        "ok": report["ok"], "entries_checked": report["entries"], "head_seq": report["head_seq"],
        "first_bad_seq": report["first_bad_seq"],
    })
    return report


@router.get("", response_model=list[LedgerEntryOut])
def read_ledger(
    limit: int = Query(100, ge=1, le=500),
    before_seq: int | None = Query(None, ge=1),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    scope = require_action(db, user, "ledger.read")
    q = select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(limit)
    if before_seq:
        q = q.where(LedgerEntry.seq < before_seq)
    if scope != ANY:
        q = q.where(LedgerEntry.case_id.in_(visible_case_ids(db, user, "ledger.read")))
    return [
        LedgerEntryOut(seq=e.seq, ts=e.ts, actor=e.actor, action=e.action, case_id=e.case_id,
                       payload=json.loads(e.payload), hash=e.hash, prev_hash=e.prev_hash)
        for e in db.scalars(q)
    ]
