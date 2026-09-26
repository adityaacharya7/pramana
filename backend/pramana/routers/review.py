"""Extraction, the review queue, intake quality issues and identity review."""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import identity, ledger, storage
from ..config import Settings
from ..db import utcnow_iso
from ..deps import current_user, get_db, get_settings
from ..extraction import engine, quality
from ..extraction.identifiers import NAMED_TYPES
from ..models import (
    Entity, EntityMention, EvidenceFile, Extraction, IdentityDecision, QualityIssue, User,
)
from ..permissions import require_case, visible_case_ids

router = APIRouter(tags=["review"])


class ExtractRequest(BaseModel):
    file_ids: list[str] | None = None


class DecisionRequest(BaseModel):
    decision: Literal["confirm", "reject"]
    scope: Literal["mention", "value", "file"] = "mention"
    types: list[str] | None = None
    extractors: list[str] | None = None


class IdentityRequest(BaseModel):
    case_id: str
    entity_a: str
    entity_b: str
    decision: Literal["MERGE", "KEEP_SEPARATE", "UNRESOLVED", "SPLIT"]
    reason: str = Field(min_length=3, max_length=1000)


class QualityRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    date_order: Literal["DMY", "MDY"] | None = None


def snippet(text: str, start: int, end: int, pad: int = 70) -> dict:
    s, e = max(0, start - pad), min(len(text), end + pad)
    return {"before": ("…" if s > 0 else "") + text[s:start], "match": text[start:end],
            "after": text[end:e] + ("…" if e < len(text) else "")}


class TextCache:
    def __init__(self, db: Session, settings: Settings):
        self.db, self.settings, self.cache = db, settings, {}

    def get(self, ev: EvidenceFile) -> str | None:
        if ev.id not in self.cache:
            try:
                self.cache[ev.id] = engine.evidence_text(self.settings, ev)
            except storage.IntegrityMismatch:
                self.cache[ev.id] = None
        return self.cache[ev.id]


# --- extraction --------------------------------------------------------------------

@router.post("/cases/{case_id}/extract")
def extract(case_id: str, body: ExtractRequest | None = None, user: User = Depends(current_user),
            db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    case = require_case(db, user, case_id, "extraction.run")
    with ledger.transaction(db):
        summary = engine.run_extraction(db, settings, case.id, body.file_ids if body else None)
        ledger.append(db, actor=user.username, action="EXTRACTION_RUN", payload={
            "case_id": case.id, "files": summary["files_processed"], "blocked": summary["files_blocked"],
            "extractions_created": summary["extractions_created"], "by_type": summary["by_type"],
            "quality_issues_open": summary["quality_issues_open"],
        })
    return summary


@router.post("/extractions/{extraction_id}/decision")
def decide_extraction(extraction_id: str, body: DecisionRequest, user: User = Depends(current_user),
                      db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    ext = db.get(Extraction, extraction_id)
    if ext is None:
        raise HTTPException(status_code=404, detail="Extraction not found.")
    ev = db.get(EvidenceFile, ext.file_id)
    require_case(db, user, ev.case_id, "extraction.decide")
    try:
        targets = engine.targets_for(db, ext, body.scope, body.types, body.extractors)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    status = "CONFIRMED" if body.decision == "confirm" else "REJECTED"
    with ledger.transaction(db):
        engine.decide(db, user.id, ev.case_id, targets, status)
        derived = engine.derive_file(db, settings, ev)
        ledger.append(db, actor=user.username, action="EXTRACTION_DECIDED", payload={
            "case_id": ev.case_id, "evidence_id": ev.id, "filename": ev.filename, "decision": status,
            "scope": body.scope, "count": len(targets), "entity_type": ext.entity_type,
            "value": ext.proposed_value, "extraction_ids": [t.id for t in targets][:200],
        })
    return {"decided": len(targets), "status": status, **derived}


# --- review queue ------------------------------------------------------------------

def _entity_card(db: Session, texts: TextCache, entity_id: str, visible: list[str]) -> dict:
    e = db.get(Entity, entity_id)
    rows = db.execute(
        select(EntityMention, Extraction, EvidenceFile)
        .join(Extraction, Extraction.id == EntityMention.extraction_id)
        .join(EvidenceFile, EvidenceFile.id == Extraction.file_id)
        .where(EntityMention.entity_id == entity_id, EntityMention.case_id.in_(visible))
        .order_by(EvidenceFile.uploaded_at, Extraction.span_start)
    ).all()
    sources, seen = [], set()
    for m, x, f in rows:
        if f.id in seen:
            continue
        seen.add(f.id)
        text = texts.get(f)
        sources.append({"evidence_id": f.id, "filename": f.filename, "case_id": f.case_id, "kind": f.kind,
                        "span": [x.span_start, x.span_end],
                        "snippet": snippet(text, x.span_start, x.span_end) if text else None})
    return {"entity_id": e.id, "type": e.type, "name": e.canonical_value, "attrs": e.attrs or {},
            "cases": sorted({m.case_id for m, _, _ in rows}), "sources": sources[:4]}


@router.get("/cases/{case_id}/review-queue")
def review_queue(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    case = require_case(db, user, case_id, "review.read")
    texts = TextCache(db, settings)
    files = db.scalars(select(EvidenceFile).where(EvidenceFile.case_id == case.id)
                       .order_by(EvidenceFile.uploaded_at)).all()
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"PENDING": 0, "CONFIRMED": 0, "REJECTED": 0})
    for fid, status, n in db.execute(
        select(Extraction.file_id, Extraction.status, func.count()).where(Extraction.file_id.in_([f.id for f in files] or [""]))
        .group_by(Extraction.file_id, Extraction.status)
    ):
        counts[fid][status] = n

    pending = db.scalars(select(Extraction).where(Extraction.file_id.in_([f.id for f in files] or [""]),
                                                  Extraction.status == "PENDING")
                         .order_by(Extraction.span_start)).all()
    groups: dict[str, dict[tuple, dict]] = defaultdict(dict)
    for x in pending:
        g = groups[x.file_id].setdefault((x.entity_type, x.proposed_value), {
            "entity_type": x.entity_type, "value": x.proposed_value, "extractor": x.extractor,
            "extraction_ids": [], "spans": [], "sample_id": x.id,
        })
        g["extraction_ids"].append(x.id)
        g["spans"].append([x.span_start, x.span_end])

    file_rows = []
    for f in files:
        text = texts.get(f) if groups.get(f.id) else None
        grp = []
        for g in groups.get(f.id, {}).values():
            s0 = g["spans"][0]
            grp.append({**g, "count": len(g["extraction_ids"]),
                        "snippet": snippet(text, s0[0], s0[1]) if text else None})
        file_rows.append({
            "evidence_id": f.id, "filename": f.filename, "kind": f.kind, "type": f.type,
            "integrity_status": f.integrity_status, "extracted": f.extracted_at is not None,
            "extractors": f.extractor_versions or [], "counts": counts[f.id], "pending_groups": grp,
        })

    issues = db.scalars(select(QualityIssue).where(QualityIssue.case_id == case.id)
                        .order_by(QualityIssue.status.desc(), QualityIssue.created_at)).all()
    visible = visible_case_ids(db, user, "graph.read")
    cands = identity.candidates(db, visible, anchor_case=case.id)
    cards: dict[str, dict] = {}
    for c in cands:
        for side in (c["a"], c["b"]):
            if side not in cards:
                cards[side] = _entity_card(db, texts, side, visible)
    return {
        "case_id": case.id,
        "files": file_rows,
        "quality_issues": [{"id": q.id, "check": q.check, "label": quality.LABELS.get(q.check, q.check),
                            "file_ids": q.file_ids, "detail": q.detail, "status": q.status,
                            "resolution": q.resolution, "decided_at": q.decided_at} for q in issues],
        "identity_candidates": [{**c, "a_card": cards[c["a"]], "b_card": cards[c["b"]]} for c in cands],
        "totals": {
            "pending_extractions": len(pending),
            "files_not_extracted": sum(1 for f in files if f.extracted_at is None),
            "open_quality_issues": sum(1 for q in issues if q.status == "OPEN"),
            "undecided_identity_candidates": sum(1 for c in cands if c["decision"] is None),
        },
    }


# --- quality issues ------------------------------------------------------------------

@router.post("/quality-issues/{issue_id}/decision")
def acknowledge_issue(issue_id: str, body: QualityRequest, user: User = Depends(current_user),
                      db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    issue = db.get(QualityIssue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Quality issue not found.")
    require_case(db, user, issue.case_id, "quality.decide")
    if issue.check == quality.AMBIGUOUS and body.date_order is None:
        raise HTTPException(status_code=422, detail="State how the dates should be read (DMY or MDY).")
    with ledger.transaction(db):
        issue.status = "ACKNOWLEDGED"
        issue.resolution = {"reason": body.reason, **({"date_order": body.date_order} if body.date_order else {})}
        issue.decided_by, issue.decided_at = user.id, utcnow_iso()
        if issue.check == quality.AMBIGUOUS:
            for fid in issue.file_ids:
                engine.derive_file(db, settings, db.get(EvidenceFile, fid))
        ledger.append(db, actor=user.username, action="QUALITY_ISSUE_ACKNOWLEDGED", payload={
            "case_id": issue.case_id, "issue_id": issue.id, "check": issue.check, "reason": body.reason,
            "date_order": body.date_order,
        })
    return {"id": issue.id, "status": issue.status, "resolution": issue.resolution}


# --- identity ------------------------------------------------------------------------

@router.post("/identities/decision")
def identity_decision(body: IdentityRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_case(db, user, body.case_id, "identity.decide")
    if body.entity_a == body.entity_b:
        raise HTTPException(status_code=422, detail="Choose two different records.")
    visible = visible_case_ids(db, user, "graph.read")
    for eid in (body.entity_a, body.entity_b):
        e = db.get(Entity, eid)
        if e is None or e.type not in NAMED_TYPES:
            raise HTTPException(status_code=404, detail="Record not found.")
        seen_in = set(db.scalars(select(EntityMention.case_id).where(EntityMention.entity_id == eid)))
        if not seen_in & set(visible):
            raise HTTPException(status_code=404, detail="Record not found.")
    a, b = identity.pair_key(body.entity_a, body.entity_b)
    current = identity.latest_decisions(db).get((a, b))
    if body.decision == "SPLIT" and (current is None or current.decision != "MERGE"):
        raise HTTPException(status_code=409, detail="Only merged records can be split.")
    with ledger.transaction(db):
        d = IdentityDecision(entity_a=a, entity_b=b, decision=body.decision, reason=body.reason,
                             user_id=user.id, decided_at=utcnow_iso())
        db.add(d)
        ledger.append(db, actor=user.username, action="IDENTITY_DECIDED", payload={
            "case_id": body.case_id, "entity_a": a, "entity_b": b, "decision": body.decision,
            "reason": body.reason, "names": [db.get(Entity, a).canonical_value, db.get(Entity, b).canonical_value],
        })
    return {"entity_a": a, "entity_b": b, "decision": body.decision}
