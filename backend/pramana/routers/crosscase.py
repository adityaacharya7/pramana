"""Cross-case matching with blind matches (F6), MO comparison (F7) and
access requests.

A match in a case the user cannot see is reported only as a count and the
owning unit. The user can raise an access request; the owning unit's
supervisor decides it. Nothing else about that case is revealed.
"""
from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ledger, storage
from ..analysis import mo
from ..config import Settings
from ..db import utcnow_iso
from ..deps import current_user, get_db, get_settings
from ..extraction import engine as xengine
from ..extraction.identifiers import ACCOUNT, IMEI, PHONE, UPI, WALLET
from ..models import AccessRequest, Case, CaseMember, Entity, EntityMention, EvidenceFile, User
from ..permissions import require_action, require_case, visible_case_ids

router = APIRouter(tags=["cross-case"])
MATCH_TYPES = (PHONE, ACCOUNT, UPI, IMEI, WALLET)
HUB_CASES = 6  # identifiers seen in more cases than this are billers/merchants: not used to suggest scope


def case_token(settings: Settings, case_id: str) -> str:
    """Opaque reference to a case the user may not see, for access requests."""
    return hmac.new(settings.jwt_secret.encode(), f"case:{case_id}".encode(), hashlib.sha256).hexdigest()[:20]


def _matches(db: Session, case_id: str) -> dict[str, dict]:
    # Distinct ids first: PostgreSQL cannot compare the JSON attrs column.
    ids = list(db.scalars(select(Entity.id).join(EntityMention, EntityMention.entity_id == Entity.id)
                          .where(EntityMention.case_id == case_id, Entity.type.in_(MATCH_TYPES)).distinct()))
    mine = db.scalars(select(Entity).where(Entity.id.in_(ids or [""]))).all()
    where: dict[str, set[str]] = defaultdict(set)
    for eid, cid in db.execute(select(EntityMention.entity_id, EntityMention.case_id)
                               .where(EntityMention.entity_id.in_(ids or [""]))):
        if cid != case_id:
            where[eid].add(cid)
    return {e.id: {"entity": e, "cases": where.get(e.id, set())} for e in mine}


@router.get("/cases/{case_id}/matches")
def matches(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
            settings: Settings = Depends(get_settings)):
    case = require_case(db, user, case_id, "graph.read")
    visible = set(visible_case_ids(db, user, "graph.read"))
    cases = {c.id: c for c in db.scalars(select(Case))}
    mine_requests = {r.case_id: r.status for r in db.scalars(select(AccessRequest).where(AccessRequest.requester == user.id))}
    out = []
    for m in _matches(db, case.id).values():
        if not m["cases"]:
            continue
        seen = sorted(c for c in m["cases"] if c in visible)
        hidden = sorted(c for c in m["cases"] if c not in visible)
        e = m["entity"]
        out.append({
            "entity_id": e.id, "type": e.type, "value": e.canonical_value,
            "names_seen": (e.attrs or {}).get("names_seen", []),
            "visible_cases": [{"id": c, "title": cases[c].title, "unit": cases[c].unit} for c in seen],
            "hidden": [{"unit": cases[c].unit, "token": case_token(settings, c),
                        "request_status": mine_requests.get(c)} for c in hidden],
            "total_cases": len(m["cases"]) + 1,
            "likely_hub": len(m["cases"]) + 1 > HUB_CASES,
        })
    out.sort(key=lambda x: (x["likely_hub"], -x["total_cases"], x["value"]))
    hidden_total = sum(len(x["hidden"]) for x in out)
    if hidden_total:
        ledger.record(db, actor=user.username, action="BLIND_MATCH_SHOWN", payload={
            "case_id": case.id, "hidden_matches": hidden_total})
    return {"case_id": case.id, "matches": out}


@router.get("/cases/{case_id}/analysis-scope")
def analysis_scope(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cases to analyse together: this case plus visible cases that share a
    non-hub identifier with it, transitively."""
    case = require_case(db, user, case_id, "analysis.run")
    visible = set(visible_case_ids(db, user, "analysis.run"))
    scope, frontier = {case.id}, [case.id]
    while frontier:
        cid = frontier.pop()
        for m in _matches(db, cid).values():
            if len(m["cases"]) + 1 > HUB_CASES:
                continue
            for other in m["cases"]:
                if other in visible and other not in scope:
                    scope.add(other)
                    frontier.append(other)
    from ..models import QualityIssue
    issues = db.scalars(select(QualityIssue).where(QualityIssue.case_id.in_(scope), QualityIssue.status == "OPEN")).all()
    cases = {c.id: c for c in db.scalars(select(Case).where(Case.id.in_(visible)))}
    return {"suggested": sorted(scope),
            "available": [{"id": c.id, "title": c.title, "city": c.city} for c in sorted(cases.values(), key=lambda c: c.id)],
            "open_quality_issues": [{"case_id": q.case_id, "check": q.check} for q in issues]}


@router.get("/cases/{case_id}/mo-matches")
def mo_matches(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings)):
    case = require_case(db, user, case_id, "graph.read")
    visible = visible_case_ids(db, user, "graph.read")
    docs, sources = {}, {}
    for f in db.scalars(select(EvidenceFile).where(EvidenceFile.case_id.in_(visible), EvidenceFile.kind == "complaint")
                        .order_by(EvidenceFile.uploaded_at)):
        if f.source_group_id != f.id:
            continue
        try:
            text = xengine.evidence_text(settings, f)
        except storage.IntegrityMismatch:
            continue
        docs[f.case_id] = docs.get(f.case_id, "") + ("\n" if f.case_id in docs else "") + text
        sources.setdefault(f.case_id, (f.id, f.filename))
    if case.id not in docs:
        return {"case_id": case.id, "method": mo.METHOD, "proposals": [], "note": "This case has no complaint yet."}
    scores = mo.mo_scores(docs)
    rule = {"min_score": 0.45, "min_attribute_types": 2}
    mine_attrs = mo.attributes(docs[case.id])
    out = []
    for (a, b), s in scores.items():
        if case.id not in (a, b):
            continue
        other = b if a == case.id else a
        oattrs = mo.attributes(docs[other])

        def passages(attrs, text):
            return [{"attribute": k, "value": x["value"], "text": text[x["span"][0]:x["span"][1]],
                     "context": text[max(0, x["span"][0] - 90):x["span"][1] + 90]}
                    for k, v in attrs.items() for x in v if f"{k}:{x['value']}" in s["shared"]]
        out.append({"case_id": other, "score": s["score"], "attribute_cosine": s["attribute_cosine"],
                    "text_cosine": s["text_cosine"], "matching_attribute_types": s["matching_attribute_types"],
                    "shared": s["shared"],
                    "proposed": s["score"] >= rule["min_score"] and len(s["matching_attribute_types"]) >= rule["min_attribute_types"],
                    "this_file": {"evidence_id": sources[case.id][0], "filename": sources[case.id][1]},
                    "other_file": {"evidence_id": sources[other][0], "filename": sources[other][1]},
                    "this_passages": passages(mine_attrs, docs[case.id]),
                    "other_passages": passages(oattrs, docs[other])})
    out.sort(key=lambda x: -x["score"])
    return {"case_id": case.id, "method": mo.METHOD, "threshold": rule,
            "note": "A similar method is a reason to compare two complaints, never evidence of a shared operation.",
            "attributes": {k: [x["value"] for x in v] for k, v in mine_attrs.items()}, "proposals": out}


# --- access requests ------------------------------------------------------------------

class AccessRequestIn(BaseModel):
    token: str | None = None
    case_id: str | None = None
    reason: str = Field(min_length=10, max_length=1000)


class AccessDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


def _request_out(db: Session, r: AccessRequest, user: User, settings: Settings) -> dict:
    case = db.get(Case, r.case_id)
    requester = db.get(User, r.requester)
    decider = db.get(User, r.decided_by) if r.decided_by else None
    can_see = r.status == "APPROVED" or user.role == "SUPERVISOR" and case.unit == user.unit
    return {"id": r.id, "status": r.status, "reason": r.reason, "created_at": r.created_at,
            "decided_at": r.decided_at, "decided_by": decider.username if decider else None,
            "requester": {"username": requester.username, "name": requester.name, "unit": requester.unit},
            "unit": case.unit, "case_id": case.id if can_see else None,
            "case_title": case.title if can_see else None, "token": case_token(settings, case.id)}


@router.post("/access-requests", status_code=201)
def create_access_request(body: AccessRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db),
                          settings: Settings = Depends(get_settings)):
    require_action(db, user, "access.request")
    target = None
    if body.token:
        target = next((c for c in db.scalars(select(Case)) if hmac.compare_digest(case_token(settings, c.id), body.token)), None)
    elif body.case_id:
        target = db.get(Case, body.case_id)
    if target is None:
        raise HTTPException(status_code=404, detail="No such case reference.")
    if db.get(CaseMember, (target.id, user.id)):
        raise HTTPException(status_code=409, detail="You already have access to this case.")
    if db.scalar(select(AccessRequest).where(AccessRequest.requester == user.id, AccessRequest.case_id == target.id,
                                             AccessRequest.status == "PENDING")):
        raise HTTPException(status_code=409, detail="A request for this case is already pending.")
    with ledger.transaction(db):
        r = AccessRequest(requester=user.id, case_id=target.id, reason=body.reason, status="PENDING",
                          created_at=utcnow_iso())
        db.add(r)
        db.flush()
        ledger.append(db, actor=user.username, action="ACCESS_REQUESTED", payload={
            "case_id": target.id, "request_id": r.id, "reason": body.reason})
    return _request_out(db, r, user, settings)


@router.get("/access-requests")
def list_access_requests(user: User = Depends(current_user), db: Session = Depends(get_db),
                         settings: Settings = Depends(get_settings)):
    mine = db.scalars(select(AccessRequest).where(AccessRequest.requester == user.id)
                      .order_by(AccessRequest.created_at.desc())).all()
    to_decide = []
    if user.role == "SUPERVISOR":
        unit_cases = [c.id for c in db.scalars(select(Case).where(Case.unit == user.unit))]
        to_decide = db.scalars(select(AccessRequest).where(AccessRequest.case_id.in_(unit_cases or [""]))
                               .order_by(AccessRequest.status.desc(), AccessRequest.created_at.desc())).all()
    return {"mine": [_request_out(db, r, user, settings) for r in mine],
            "to_decide": [_request_out(db, r, user, settings) for r in to_decide]}


@router.post("/access-requests/{request_id}/decision")
def decide_access_request(request_id: str, body: AccessDecision, user: User = Depends(current_user),
                          db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    require_action(db, user, "access.decide")
    r = db.get(AccessRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    case = db.get(Case, r.case_id)
    if case.unit != user.unit:
        ledger.record(db, actor=user.username, action="ACCESS_REFUSED", payload={
            "case_id": case.id, "attempted": "access.decide", "reason": "not the owning unit's supervisor"})
        raise HTTPException(status_code=403, detail="Only the owning unit's supervisor decides this request.")
    if r.status != "PENDING":
        raise HTTPException(status_code=409, detail="This request has already been decided.")
    with ledger.transaction(db):
        r.status = "APPROVED" if body.decision == "approve" else "REJECTED"
        r.decided_by, r.decided_at = user.id, utcnow_iso()
        if r.status == "APPROVED" and not db.get(CaseMember, (case.id, r.requester)):
            db.add(CaseMember(case_id=case.id, user_id=r.requester, access="member", granted_at=r.decided_at,
                              granted_by=user.username))
        ledger.append(db, actor=user.username, action=f"ACCESS_{r.status}", payload={
            "case_id": case.id, "request_id": r.id, "requester": db.get(User, r.requester).username,
            "reason": body.reason})
    return _request_out(db, r, user, settings)
