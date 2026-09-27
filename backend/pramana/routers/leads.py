"""Analysis runs, leads and their Evidence Receipts, the lead lifecycle,
Challenge Mode, the Amount & Draft Assistant, the money trail, and handover
packs."""
from __future__ import annotations

import base64
import json
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis import bundle as bundle_mod
from ..analysis import pdf as pdf_mod
from ..analysis import service
from ..analysis.rules import RULES
from ..analysis.trail import METHOD_TEXT, METHODS
from ..config import Settings
from ..deps import current_user, get_db, get_settings
from ..models import ActionDraft, Lead, Scenario, User
from ..permissions import require_action, require_case, require_cases, visible_case_ids

router = APIRouter(tags=["analysis"])


class RunIn(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=60)


class TransitionIn(BaseModel):
    action: Literal["propose", "approve", "reject"] = "propose"
    to: str | None = None
    reason: str = Field(min_length=3, max_length=1000)


class ChallengeIn(BaseModel):
    operations: list[dict] = Field(min_length=1, max_length=10)


class ScenarioActionIn(BaseModel):
    action: Literal["propose", "approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


class DraftsIn(BaseModel):
    method: Literal["fifo", "lifo", "prorata"]


class ApproveIn(BaseModel):
    reason: str = Field("Reviewed", min_length=3, max_length=1000)


def _refused(e: service.Refused) -> HTTPException:
    return HTTPException(status_code=409, detail=str(e))


def _lead(db: Session, user: User, lead_id: str, action: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    require_cases(db, user, service.lead_cases(db, lead), action)
    return lead


@router.get("/rules")
def rules(user: User = Depends(current_user)):
    return {"rules": [{"id": k, "title": v["title"], "params": v["params"]} for k, v in RULES.items()],
            "attribution_methods": [{"id": m, "text": METHOD_TEXT[m]} for m in METHODS]}


@router.post("/analysis/run")
def run(body: RunIn, user: User = Depends(current_user), db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings)):
    require_cases(db, user, body.case_ids, "analysis.run")
    try:
        return service.run_analysis(db, settings, user, body.case_ids)
    except service.Refused as e:
        raise _refused(e)


@router.get("/cases/{case_id}/leads")
def case_leads(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_case(db, user, case_id, "lead.read")
    visible = set(visible_case_ids(db, user, "lead.read"))
    out = []
    for lead in db.scalars(select(Lead).order_by(Lead.rule_id, Lead.key)):
        cases = service.lead_cases(db, lead)
        if case_id in lead.case_ids and set(cases) <= visible:
            out.append(service.lead_out(db, lead))
    return out


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings)):
    return service.lead_detail(db, settings, _lead(db, user, lead_id, "lead.read"))


@router.get("/leads/{lead_id}/receipt")
def lead_receipt(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    detail = service.lead_detail(db, settings, _lead(db, user, lead_id, "lead.read"))
    if detail["receipt"] is None:
        raise HTTPException(status_code=409, detail="This lead is not produced by the current analysis.")
    return detail["receipt"]


@router.post("/leads/{lead_id}/transition")
def lead_transition(lead_id: str, body: TransitionIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id, "lead.transition")
    if body.action == "propose" and body.to not in service.STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of {service.STATUSES}.")
    try:
        return service.transition(db, user, lead, body.action, body.to, body.reason)
    except service.Refused as e:
        raise _refused(e)


@router.post("/leads/{lead_id}/challenge")
def lead_challenge(lead_id: str, body: ChallengeIn, user: User = Depends(current_user), db: Session = Depends(get_db),
                   settings: Settings = Depends(get_settings)):
    lead = _lead(db, user, lead_id, "lead.challenge")
    try:
        sc = service.challenge(db, settings, user, lead, body.operations)
    except service.Refused as e:
        raise HTTPException(status_code=422, detail=str(e))
    return service.scenario_out(db, sc)


@router.post("/scenarios/{scenario_id}/apply")
def scenario_apply(scenario_id: str, body: ScenarioActionIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    sc = db.get(Scenario, scenario_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    require_cases(db, user, sc.case_ids, "scenario.decide")
    try:
        return service.scenario_action(db, settings, user, sc, body.action, body.reason)
    except service.Refused as e:
        raise _refused(e)


@router.post("/leads/{lead_id}/action-drafts")
def create_drafts(lead_id: str, body: DraftsIn, user: User = Depends(current_user), db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    lead = _lead(db, user, lead_id, "draft.create")
    try:
        return service.create_drafts(db, settings, user, lead, body.method)
    except service.Refused as e:
        raise _refused(e)


@router.post("/action-drafts/{draft_id}/approve")
def approve_draft(draft_id: str, body: ApproveIn | None = None, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    d = db.get(ActionDraft, draft_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    require_cases(db, user, d.case_ids or [], "draft.approve")
    try:
        return service.approve_draft(db, user, d, (body or ApproveIn()).reason)
    except service.Refused as e:
        raise _refused(e)


@router.get("/cases/{case_id}/money-trail")
def money_trail(case_id: str, cases: str | None = None, user: User = Depends(current_user),
                db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    scope = sorted({case_id, *[c for c in (cases or "").split(",") if c]})
    require_cases(db, user, scope, "graph.read")
    inp, result = service.live(db, settings, scope)
    return {"cases": scope, "trail": result["trail"], "labels": service.labels_for(inp, result),
            "method_text": METHOD_TEXT, "reconciles": result["reconciles"], "operations": result["operations"],
            "note": "Estimates, not facts. Totals never exceed the victims' loss; a range across methods is not a "
                    "confidence interval; holdings are 'as of' the statement end date, not current balances."}


@router.get("/leads/{lead_id}/export")
def export_json(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings)):
    lead = _lead(db, user, lead_id, "lead.export")
    try:
        bundle = service.export_bundle(db, settings, user, lead)
    except service.Refused as e:
        raise _refused(e)
    name = f"pramana-handover-{lead.rule_id}-{lead.id[:8]}.json"
    return Response(json.dumps(bundle, indent=1, ensure_ascii=False, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/leads/{lead_id}/export.pdf")
def export_pdf(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings)):
    lead = _lead(db, user, lead_id, "lead.export")
    try:
        bundle = service.export_bundle(db, settings, user, lead)
    except service.Refused as e:
        raise _refused(e)
    name = f"pramana-handover-{lead.rule_id}-{lead.id[:8]}.pdf"
    return Response(pdf_mod.render(bundle), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/bundles/verify")
def verify_bundle(bundle: dict = Body(...), user: User = Depends(current_user), db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    require_action(db, user, "bundle.verify")
    from ..checkpoints import enabled, keyring_for
    try:
        trusted = keyring_for(settings).public_key() if enabled(settings) else None
    except Exception:  # noqa: BLE001 - no key on this deployment: fall back to the bundle's own key
        trusted = None
    try:
        report = bundle_mod.verify_bundle(bundle, trusted_public_key=trusted)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Not a readable PRAMANA bundle ({e}).")
    from .. import ledger
    ledger.record(db, actor=user.username, action="BUNDLE_VERIFIED", payload={
        "lead": report.get("lead"), "ok": report["ok"], "bundle_hash": bundle.get("bundle_hash")})
    return report


@router.get("/ledger/checkpoint")
def latest_checkpoint(user: User = Depends(current_user), db: Session = Depends(get_db),
                      settings: Settings = Depends(get_settings)):
    require_action(db, user, "ledger.verify")
    from ..checkpoints import _raw_pub, enabled, keyring_for, latest_retained
    if not enabled(settings):
        return {"checkpoint": None, "trusted_public_key": None}
    kr = keyring_for(settings)
    cp = latest_retained(kr)
    pub = base64.b64encode(_raw_pub(kr.public_key())).decode()
    return {"checkpoint": cp, "trusted_public_key": pub}


@router.post("/ledger/verify")
def verify_with_checkpoint(checkpoint: dict = Body(...), user: User = Depends(current_user),
                           db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Verify against a checkpoint you retained yourself (e.g. from a handover
    pack or the supervisor's copy)."""
    require_action(db, user, "ledger.verify")
    from .. import ledger
    from ..checkpoints import enabled, keyring_for
    if not enabled(settings):
        raise HTTPException(status_code=409, detail="Checkpoints are not configured on this deployment.")
    report = ledger.verify(db, keyring_for(settings), checkpoint=checkpoint)
    ledger.record(db, actor=user.username, action="LEDGER_VERIFIED", payload={
        "ok": report["ok"], "head_seq": report["head_seq"], "against_checkpoint": checkpoint.get("seq")})
    return report
