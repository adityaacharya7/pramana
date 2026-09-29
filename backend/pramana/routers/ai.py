"""PRAMANA AI Router — Deeply integrated Gemini AI Endpoints."""
from __future__ import annotations

import json
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
    load_all_cases,
    load_ground_truth,
    GEMINI_MODELS,
)
from ..deps import current_user, get_db
from ..db import utcnow_iso
from ..models import Case, Entity, EvidenceFile, Lead, Transaction, User

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
    return {
        "status": "online",
        "provider": "Google Gemini",
        "active_models": GEMINI_MODELS,
        "capabilities": [
            "Omniscient Case & Syndicate Cross-Referencing",
            "Modus Operandi & Typology Deep Profiling",
            "Statutory Legal Notice Drafting (Sec 94 & 106 BNSS)",
            "Automated Multi-Tier Money Trail Attribution",
            "Real-time Cryptographic Audit Ledger Recording",
        ],
    }


@router.post("/chat")
def ai_chat(
    body: ChatRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Interactive AI Copilot chat grounded in all cases, persons, and money trails."""
    # 1. Identify all target cases (from active case_id or mentioned in message)
    target_case_ids = set()
    if body.case_id:
        target_case_ids.add(body.case_id.upper())
    
    found_in_msg = re.findall(r"C-\d{3}", body.message.upper())
    target_case_ids.update(found_in_msg)

    # 2. Extract database context for target cases
    db_extra_parts = []
    
    if target_case_ids:
        cases_in_db = db.scalars(
            select(Case).where(Case.id.in_(list(target_case_ids)))
        ).all()
        
        for c in cases_in_db:
            ev_count = db.scalar(
                select(func.count()).select_from(EvidenceFile).where(EvidenceFile.case_id == c.id)
            ) or 0
            
            db_extra_parts.append(
                f"DATABASE CASE RECORD: [{c.id}] FIR {c.fir_no} | Station: {c.station} | "
                f"Complainant: {c.complainant} | City: {c.city} | Reg Date: {c.registered_on} | "
                f"Evidence Files Sealed: {ev_count} | Status: {c.status}"
            )
            
            # Fetch relevant leads linked to this case
            leads = db.scalars(
                select(Lead).limit(10)
            ).all()
            for l in leads:
                if c.id in (l.case_ids or []):
                    db_extra_parts.append(
                        f"  -> ACTIVE INVESTIGATION LEAD [{l.rule_id}]: {l.title} (Status: {l.status}) | {l.detail}"
                    )

    # 3. If query mentions key persons, search entities
    keywords = ["vivek", "chauhan", "balaji", "aakash", "jain", "sandeep", "rahul", "pooja", "shobha", "harish", "kavitha", "p-77", "6577461070"]
    lower_msg = body.message.lower()
    matched_kw = [k for k in keywords if k in lower_msg]
    if matched_kw:
        matched_entities = db.scalars(
            select(Entity).limit(15)
        ).all()
        for e in matched_entities:
            for kw in matched_kw:
                if kw in e.canonical_value.lower():
                    db_extra_parts.append(f"DATABASE ENTITY MATCH: {e.type} -> '{e.canonical_value}'")

    # 4. Contextual summary of primary case if active
    case_context = None
    primary_id = body.case_id or (list(target_case_ids)[0] if target_case_ids else None)
    if primary_id:
        p_case = db.get(Case, primary_id)
        if p_case:
            ev_cnt = db.scalar(
                select(func.count()).select_from(EvidenceFile).where(EvidenceFile.case_id == p_case.id)
            ) or 0
            case_context = {
                "id": p_case.id,
                "fir_no": p_case.fir_no,
                "title": p_case.title,
                "complainant": p_case.complainant,
                "city": p_case.city,
                "station": p_case.station,
                "unit": p_case.unit,
                "status": p_case.status,
                "registered_on": p_case.registered_on,
                "evidence_count": ev_cnt,
            }

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

    # Record AI query into cryptographic audit ledger
    with ledger.transaction(db):
        ledger.append(db, actor=user.username, action="AI_COPILOT_QUERY", payload={
            "case_id": primary_id,
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
    """Deep forensic intelligence analysis of a specific case."""
    case = db.get(Case, body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    ev_files = db.scalars(
        select(EvidenceFile).where(EvidenceFile.case_id == case.id)
    ).all()

    evidence_info = [
        {"filename": ev.filename, "kind": ev.kind, "bytes": ev.size_bytes} for ev in ev_files
    ]

    entities = db.scalars(select(Entity).limit(20)).all()
    entity_info = [{"type": e.type, "name": e.canonical_value} for e in entities]

    case_info = {
        "id": case.id,
        "fir_no": case.fir_no,
        "title": case.title,
        "complainant": case.complainant,
        "city": case.city,
        "station": case.station,
        "evidence": evidence_info,
        "entities": entity_info,
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
    """Draft court-ready statutory notices (Section 94 or 106 BNSS, 69A IT Act)."""
    case = db.get(Case, body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = {
        "station": case.station or f"{case.city or case.unit} Cyber Crime PS",
        "city": case.city or "Mumbai",
        "fir_no": case.fir_no,
        "registered_on": case.registered_on,
        "complainant": case.complainant,
    }

    target_entity = {
        "name": body.entity_name,
        "account_no": body.entity_identifier,
        "amount": body.amount or "78,000",
        "utr": body.utr or "IMPS/UTR Ref: 620746847120",
        "ifsc": body.ifsc or "XSSB0000017",
    }

    officer_data = {
        "name": user.name,
        "role_label": user.role_label,
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
