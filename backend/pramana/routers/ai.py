"""PRAMANA AI Router — Gemini endpoints.

The model only ever sees records the signed-in user could open themselves:
every case is checked against the permission matrix, and leads or entities
are drawn only from those cases. Nothing about out-of-scope cases, and no
dataset answer key, is put into a prompt."""
from __future__ import annotations

import json
import os
import re
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import ledger
from ..ai import (
    analyze_case_deep,
    chat_case_intelligence,
    draft_statutory_notice,
    GEMINI_MODELS,
)
from ..deps import current_user, get_db
from ..db import utcnow_iso
from ..models import Case, Entity, EntityMention, EvidenceFile, Lead, User
from ..permissions import ROLE_LABELS, Role, require_case, visible_case_ids

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    case_id: str | None = None
    history: list[dict[str, str]] | None = None


class CaseAnalysisRequest(BaseModel):
    case_id: str = Field(min_length=1)


class DraftNoticeRequest(BaseModel):
    case_id: str = Field(min_length=1)
    notice_type: str = Field(default="SECTION_106_BNSS")
    entity_name: str = Field(min_length=1)
    entity_identifier: str = Field(min_length=1)
    amount: str | None = None
    utr: str | None = None
    ifsc: str | None = None


@router.get("/status")
def ai_status(user: User = Depends(current_user)):
    """Health check for AI capabilities and active models."""
    has_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    return {
        "status": "online" if has_key else "unconfigured",
        "provider": "Google Gemini",
        "has_api_key": has_key,
        "active_models": GEMINI_MODELS,
        "capabilities": [
            "Case Cross-Referencing (within your authorised cases)",
            "Modus Operandi & Typology Deep Profiling",
            "Statutory Legal Notice Drafting (Sec 94 & 106 BNSS)",
            "Automated Multi-Tier Money Trail Attribution",
            "Real-time Cryptographic Audit Ledger Recording",
        ],
    }


def _case_summary(db: Session, case: Case) -> dict[str, Any]:
    ev_count = db.scalar(
        select(func.count()).select_from(EvidenceFile).where(EvidenceFile.case_id == case.id)
    ) or 0
    return {
        "id": case.id,
        "fir_no": case.fir_no,
        "title": case.title,
        "complainant": case.complainant,
        "city": case.city,
        "station": case.station,
        "unit": case.unit,
        "status": case.status,
        "registered_on": case.registered_on,
        "evidence_count": ev_count,
    }


def _visible_leads(db: Session, user: User, case_id: str) -> list[Lead]:
    """Active leads on this case whose every case the user may read (a lead
    spanning cases needs all of them, as in the leads router)."""
    readable = set(visible_case_ids(db, user, "lead.read"))
    leads = db.scalars(select(Lead).where(Lead.active.is_(True)).order_by(Lead.created_at)).all()
    return [l for l in leads if case_id in (l.case_ids or []) and set(l.case_ids or []) <= readable]


def _case_entities(db: Session, case_id: str, limit: int = 40) -> list[Entity]:
    """Confirmed entities mentioned in this case's evidence."""
    return list(db.scalars(
        select(Entity)
        .where(Entity.id.in_(select(EntityMention.entity_id).where(EntityMention.case_id == case_id)))
        .order_by(Entity.type, Entity.canonical_value)
        .limit(limit)
    ))


@router.post("/chat")
def ai_chat(
    body: ChatRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Copilot chat grounded in the cases this user is authorised to view."""
    # The screen's case must be in scope (refused and logged otherwise).
    primary: Case | None = None
    if body.case_id:
        primary = require_case(db, user, body.case_id.upper(), "case.view")

    # Cases named in the message are used only if the user could open them;
    # others are dropped silently so the reply reveals nothing about them.
    visible = set(visible_case_ids(db, user, "case.view"))
    target_ids = {c for c in re.findall(r"C-\d{3}", body.message.upper()) if c in visible}
    if primary is not None:
        target_ids.add(primary.id)

    db_extra_parts: list[str] = []
    for cid in sorted(target_ids):
        c = db.get(Case, cid)
        if c is None:
            continue
        summ = _case_summary(db, c)
        db_extra_parts.append(
            f"DATABASE CASE RECORD: [{c.id}] FIR {c.fir_no} | Station: {c.station} | "
            f"Complainant: {c.complainant} | City: {c.city} | Reg Date: {c.registered_on} | "
            f"Evidence Files Sealed: {summ['evidence_count']} | Status: {c.status}"
        )
        for l in _visible_leads(db, user, c.id):
            db_extra_parts.append(
                f"  -> LEAD [{l.rule_id}]: {l.title} (Status: {l.status}) | {json.dumps(l.detail, default=str)[:800]}"
            )
        ents = _case_entities(db, c.id, limit=25)
        if ents:
            db_extra_parts.append(
                "  -> CONFIRMED ENTITIES: " + "; ".join(f"{e.type}: {e.canonical_value}" for e in ents)
            )

    if primary is None and target_ids:
        primary = db.get(Case, sorted(target_ids)[0])
    case_context = _case_summary(db, primary) if primary is not None else None
    primary_id = primary.id if primary is not None else None
    db_extra_context = "\n".join(db_extra_parts) if db_extra_parts else None

    try:
        reply = chat_case_intelligence(
            body.message,
            case_context=case_context,
            history=body.history,
            db_extra_context=db_extra_context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {exc}",
        )

    with ledger.transaction(db):
        ledger.append(db, actor=user.username, action="AI_COPILOT_QUERY", payload={
            "case_id": primary_id,
            "context_case_ids": sorted(target_ids),
            "query_preview": body.message[:120],
            "officer": user.name,
        })

    return {
        "reply": reply,
        "case_id": primary_id,
        "officer": user.name,
        "timestamp": utcnow_iso(),
    }


@router.post("/case-analysis")
def ai_case_analysis(
    body: CaseAnalysisRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """AI-assisted analysis of one case, from that case's own records."""
    case = require_case(db, user, body.case_id.upper(), "analysis.run")

    ev_files = db.scalars(
        select(EvidenceFile).where(EvidenceFile.case_id == case.id)
    ).all()

    case_info = {
        **_case_summary(db, case),
        "evidence": [{"filename": ev.filename, "kind": ev.kind, "bytes": ev.size_bytes} for ev in ev_files],
        "entities": [{"type": e.type, "name": e.canonical_value} for e in _case_entities(db, case.id)],
        "leads": [
            {"rule": l.rule_id, "title": l.title, "status": l.status, "detail": l.detail}
            for l in _visible_leads(db, user, case.id)
        ],
    }

    try:
        analysis = analyze_case_deep(case_info)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Analysis error: {exc}",
        )

    with ledger.transaction(db):
        ledger.append(db, actor=user.username, action="AI_CASE_ANALYSIS", payload={
            "case_id": case.id,
            "typology": analysis.get("typology"),
            "confidence": analysis.get("confidence"),
        })

    return {
        "case_id": case.id,
        "analysis": analysis,
        "analyzed_at": utcnow_iso(),
    }


@router.post("/draft-notice")
def ai_draft_notice(
    body: DraftNoticeRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Draft a statutory notice (Section 94 or 106 BNSS, 69A IT Act) for the officer to review."""
    case = require_case(db, user, body.case_id.upper(), "draft.create")

    case_data = {
        "station": case.station or f"{case.city or case.unit} Cyber Crime PS",
        "city": case.city,
        "fir_no": case.fir_no,
        "registered_on": case.registered_on,
        "complainant": case.complainant,
    }

    # Only what the officer supplied; missing details stay blank in the draft
    # rather than being filled with invented figures.
    target_entity = {
        "name": body.entity_name,
        "account_no": body.entity_identifier,
        "amount": body.amount,
        "utr": body.utr,
        "ifsc": body.ifsc,
    }

    officer_data = {
        "name": user.name,
        "role_label": ROLE_LABELS[Role(user.role)],
        "unit": user.unit,
    }

    try:
        notice_text = draft_statutory_notice(body.notice_type, case_data, target_entity, officer_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Notice drafting error: {exc}",
        )

    with ledger.transaction(db):
        ledger.append(db, actor=user.username, action="AI_NOTICE_DRAFTED", payload={
            "case_id": case.id,
            "notice_type": body.notice_type,
            "entity": body.entity_name,
        })

    return {
        "case_id": case.id,
        "notice_type": body.notice_type,
        "target": body.entity_name,
        "notice_text": notice_text,
        "drafted_at": utcnow_iso(),
    }
