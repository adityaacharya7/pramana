"""Database side of analysis: runs and leads, the lead lifecycle, Challenge
Mode scenarios and their reviewed application, draft sets, and exports.

Every write here goes through the ledger in the same transaction.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import checkpoints, ledger
from ..config import Settings
from ..db import utcnow_iso
from ..models import ActionDraft, EvidenceFile, LedgerEntry, Lead, QualityIssue, RuleRun, Scenario, Snapshot, User, new_id
from . import bundle as bundle_mod
from .drafts import build_draft_set
from .engine import analyse, dependencies, diff, receipt, sources_of, summary
from .inputs import applied_operations, build_input
from .model import build_model
from .rules import RULES, party_label, rule_versions

STATUSES = ("DETECTED", "UNDER_VERIFICATION", "VERIFIED", "DISMISSED", "NEEDS_EVIDENCE")
ALLOWED = {
    "DETECTED": {"UNDER_VERIFICATION", "DISMISSED"},
    "UNDER_VERIFICATION": {"VERIFIED", "DISMISSED", "NEEDS_EVIDENCE"},
    "NEEDS_EVIDENCE": {"UNDER_VERIFICATION", "DISMISSED"},
    "VERIFIED": {"UNDER_VERIFICATION"},
    "DISMISSED": {"UNDER_VERIFICATION"},
}
OPS = {"exclude_source": "source", "dispute_txn": "event_id", "simulate_no_txn": "event_id"}


class Refused(ValueError):
    pass


def live(db: Session, settings: Settings, case_ids: list[str]) -> tuple[dict, dict]:
    inp = build_input(db, settings, case_ids)
    return inp, analyse(inp, applied_operations(db, case_ids))


def open_issues(db: Session, case_ids: list[str]) -> list[QualityIssue]:
    return db.scalars(select(QualityIssue).where(QualityIssue.case_id.in_(case_ids),
                                                 QualityIssue.status == "OPEN")).all()


def lead_cases(db: Session, lead: Lead) -> list[str]:
    run = db.get(RuleRun, lead.rule_run_id)
    return sorted(set(run.case_ids or lead.case_ids))


def lead_context(db: Session, settings: Settings, lead: Lead) -> tuple[dict, dict, dict | None]:
    inp, result = live(db, settings, lead_cases(db, lead))
    obs = next((o for o in result["observations"] if o["key"] == lead.key), None)
    return inp, result, obs


def labels_for(inp: dict, result: dict) -> dict[str, str]:
    model = build_model(inp, result.get("operations"))
    parties = {h["party"] for m in result["trail"]["methods"].values() for h in m["holdings"]}
    parties |= {f["from"] for m in result["trail"]["methods"].values() for f in m["flows"]}
    return {p: party_label(model, p) for p in parties}


# --- runs and leads ---------------------------------------------------------------

def persist_run(db: Session, user: User, case_ids: list[str], result: dict) -> dict:
    now = utcnow_iso()
    runs = {}
    for rid, spec in RULES.items():
        run = RuleRun(rule_id=rid, version=rule_versions()[rid], params=result["params"].get(rid, {}), run_at=now,
                      case_ids=sorted(case_ids), run_by=user.id)
        db.add(run)
        runs[rid] = run
    db.flush()
    produced, created, updated = set(), 0, 0
    for o in result["observations"]:
        produced.add(o["key"])
        lead = db.scalar(select(Lead).where(Lead.key == o["key"]))
        detail = {k: o[k] for k in ("subject", "summary", "metrics", "independent_sources", "support")}
        if lead is None:
            db.add(Lead(key=o["key"], rule_id=o["rule_id"], title=o["title"], observation=o["summary"],
                        rule_run_id=runs[o["rule_id"]].id, case_ids=o["cases"], detail=detail, status="DETECTED",
                        owner=user.id, created_at=now, updated_at=now, active=True))
            created += 1
        else:
            lead.observation, lead.detail, lead.case_ids = o["summary"], detail, o["cases"]
            lead.rule_run_id, lead.active, lead.updated_at, lead.title = runs[o["rule_id"]].id, True, now, o["title"]
            updated += 1
    inactive = 0
    for lead in db.scalars(select(Lead).where(Lead.active.is_(True))):
        if lead.key not in produced and set(lead.case_ids) <= set(case_ids):
            lead.active, lead.updated_at = False, now
            inactive += 1
    return {"created": created, "updated": updated, "no_longer_produced": inactive,
            "observations": len(result["observations"])}


def run_analysis(db: Session, settings: Settings, user: User, case_ids: list[str], actor: str | None = None) -> dict:
    issues = open_issues(db, case_ids)
    if issues:
        raise Refused("Open intake quality issues must be reviewed before analysis: "
                      + "; ".join(f"{q.case_id} {q.check.replace('_', ' ')}" for q in issues))
    inp, result = live(db, settings, case_ids)
    with ledger.transaction(db):
        counts = persist_run(db, user, case_ids, result)
        by_rule: dict[str, int] = {}
        for o in result["observations"]:
            by_rule[o["rule_id"]] = by_rule.get(o["rule_id"], 0) + 1
        ledger.append(db, actor=actor or user.username, action="ANALYSIS_RUN", payload={
            "case_id": sorted(case_ids)[0], "cases": sorted(case_ids), "input_hash": result["input_hash"],
            "rule_versions": result["rule_versions"], "by_rule": by_rule, **counts,
            "operations_applied": len(result["operations"]),
        })
    return {**counts, "by_rule": by_rule, "input_hash": result["input_hash"], "reconciles": result["reconciles"]}


def lead_out(db: Session, lead: Lead) -> dict:
    pending_by = db.get(User, lead.pending_by) if lead.pending_by else None
    return {"id": lead.id, "key": lead.key, "rule_id": lead.rule_id, "title": lead.title,
            "observation": lead.observation, "status": lead.status, "active": lead.active,
            "case_ids": lead.case_ids, "analysis_cases": lead_cases(db, lead),
            "subject": (lead.detail or {}).get("subject"), "metrics": (lead.detail or {}).get("metrics"),
            "independent_sources": (lead.detail or {}).get("independent_sources"),
            "pending": {"status": lead.pending_status, "reason": lead.pending_reason,
                        "by": pending_by.username if pending_by else None} if lead.pending_status else None,
            "updated_at": lead.updated_at}


# --- lifecycle ------------------------------------------------------------------------

def transition(db: Session, user: User, lead: Lead, action: str, to: str | None, reason: str) -> dict:
    is_sup = user.role == "SUPERVISOR"
    with ledger.transaction(db):
        if action == "propose":
            if to not in ALLOWED.get(lead.status, set()):
                raise Refused(f"A lead in {lead.status} cannot move to {to}.")
            if is_sup:
                prev, lead.status = lead.status, to
                lead.pending_status = lead.pending_reason = lead.pending_by = None
                ledger.append(db, actor=user.username, action="LEAD_STATUS_CHANGED", payload={
                    "case_id": lead.case_ids[0], "lead_id": lead.id, "lead": lead.key, "from": prev, "to": to,
                    "reason": reason, "proposed_by": user.username, "approved_by": user.username})
                done = "applied"
            else:
                lead.pending_status, lead.pending_reason, lead.pending_by = to, reason, user.id
                ledger.append(db, actor=user.username, action="LEAD_STATUS_PROPOSED", payload={
                    "case_id": lead.case_ids[0], "lead_id": lead.id, "lead": lead.key, "from": lead.status,
                    "to": to, "reason": reason})
                done = "proposed"
        elif action in ("approve", "reject"):
            if not is_sup:
                raise Refused("Only a supervisory officer can decide a proposed status change.")
            if not lead.pending_status:
                raise Refused("There is no proposed change to decide.")
            proposer = db.get(User, lead.pending_by)
            if action == "approve":
                prev, lead.status = lead.status, lead.pending_status
                ledger.append(db, actor=user.username, action="LEAD_STATUS_CHANGED", payload={
                    "case_id": lead.case_ids[0], "lead_id": lead.id, "lead": lead.key, "from": prev,
                    "to": lead.status, "reason": lead.pending_reason, "decision_note": reason,
                    "proposed_by": proposer.username if proposer else None, "approved_by": user.username})
            else:
                ledger.append(db, actor=user.username, action="LEAD_STATUS_REJECTED", payload={
                    "case_id": lead.case_ids[0], "lead_id": lead.id, "lead": lead.key,
                    "proposed": lead.pending_status, "reason": reason,
                    "proposed_by": proposer.username if proposer else None})
            lead.pending_status = lead.pending_reason = lead.pending_by = None
            done = action + "d" if action == "approve" else "rejected"
        else:
            raise Refused(f"Unknown action {action!r}.")
        lead.updated_at = utcnow_iso()
    if done in ("applied", "approved"):
        checkpoints.take(db, f"lead status change ({lead.key})")
    return {"result": done, "status": lead.status}


# --- Challenge Mode -------------------------------------------------------------------

def validate_ops(operations: list[dict]) -> list[dict]:
    clean = []
    for op in operations:
        kind = op.get("op")
        if kind not in OPS or not op.get(OPS[kind]):
            raise Refused(f"Operation must be one of {sorted(OPS)} with a {OPS.get(kind, 'target')}.")
        clean.append({"op": kind, OPS[kind]: str(op[OPS[kind]]), **({"note": op["note"]} if op.get("note") else {})})
    return clean


def affected_drafts(db: Session, case_ids: list[str], before: dict, after: dict, operations: list[dict]) -> list[dict]:
    excluded = {o["source"] for o in operations if o["op"] == "exclude_source"}
    changed_keys = {x["key"] for x in diff(before, after)["removed"]} | {x["key"] for x in diff(before, after)["changed"]}
    moved = {e["party"] for e in diff(before, after)["estimates"]}
    out = []
    for d in db.scalars(select(ActionDraft).where(ActionDraft.status.in_(["DRAFT", "APPROVED"]))):
        if not set(d.case_ids or []) & set(case_ids):
            continue
        lead = db.get(Lead, d.lead_id)
        why = []
        if set(d.sources or []) & excluded:
            why.append("rests on an excluded record")
        if lead and lead.key in changed_keys:
            why.append("its lead changes")
        if d.account_id in moved:
            why.append("its estimate changes")
        if why:
            out.append({"draft_id": d.id, "account_id": d.account_id, "status": d.status, "lead": lead.key if lead else None,
                        "amount": float(d.amount or 0), "why": "; ".join(why)})
    return out


def challenge(db: Session, settings: Settings, user: User, lead: Lead, operations: list[dict]) -> Scenario:
    ops = validate_ops(operations)
    cases = lead_cases(db, lead)
    inp, before = live(db, settings, cases)
    after = analyse(inp, before["operations"] + ops)
    d = diff(before, after)
    deps = []
    for op in ops:
        if op["op"] == "exclude_source":
            deps.append({"source": op["source"], "findings": dependencies(before, op["source"])})
    d["dependencies"] = deps
    d["affected_drafts"] = affected_drafts(db, cases, before, after, ops)
    if "without_disputed" in after:
        d["without_disputed"] = diff(before, {**after, **after["without_disputed"],
                                             "params": after["params"], "near_misses": {}})
    with ledger.transaction(db):
        sc = Scenario(lead_id=lead.id, case_ids=cases, input_hash=before["input_hash"], operations=ops,
                      reconciles=after["reconciles"], result_diff=d, status="sandbox", created_at=utcnow_iso())
        db.add(sc)
        db.flush()
        ledger.append(db, actor=user.username, action="CHALLENGE_RUN", payload={
            "case_id": cases[0], "cases": cases, "lead": lead.key, "scenario_id": sc.id, "operations": ops,
            "findings_removed": len(d["removed"]), "findings_changed": len(d["changed"]),
            "reconciles_after": after["reconciles"], "live_case_changed": False})
    return sc


def scenario_out(db: Session, sc: Scenario) -> dict:
    who = lambda uid: (db.get(User, uid).username if uid else None)  # noqa: E731
    return {"id": sc.id, "lead_id": sc.lead_id, "case_ids": sc.case_ids, "operations": sc.operations,
            "status": sc.status, "reconciles": sc.reconciles, "diff": sc.result_diff, "created_at": sc.created_at,
            "proposed_by": who(sc.proposed_by), "approved_by": who(sc.approved_by),
            "proposal_reason": sc.proposal_reason, "decision_reason": sc.decision_reason, "decided_at": sc.decided_at}


def scenario_action(db: Session, settings: Settings, user: User, sc: Scenario, action: str, reason: str) -> dict:
    is_sup = user.role == "SUPERVISOR"
    if action == "propose":
        if sc.status != "sandbox":
            raise Refused("Only a sandbox scenario can be proposed.")
        with ledger.transaction(db):
            sc.status, sc.proposed_by, sc.proposal_reason = "proposed", user.id, reason
            ledger.append(db, actor=user.username, action="SCENARIO_PROPOSED", payload={
                "case_id": sc.case_ids[0], "scenario_id": sc.id, "operations": sc.operations, "reason": reason})
        return scenario_out(db, sc)
    if not is_sup:
        raise Refused("Only a supervisory officer can apply a scenario to the case.")
    if sc.status != "proposed":
        raise Refused("The scenario must be proposed by an officer first.")
    if action == "reject":
        with ledger.transaction(db):
            sc.status, sc.approved_by, sc.decision_reason, sc.decided_at = "rejected", user.id, reason, utcnow_iso()
            ledger.append(db, actor=user.username, action="SCENARIO_REJECTED", payload={
                "case_id": sc.case_ids[0], "scenario_id": sc.id, "reason": reason})
        return scenario_out(db, sc)
    if action != "approve":
        raise Refused(f"Unknown action {action!r}.")

    inp, before = live(db, settings, sc.case_ids)
    after = analyse(inp, before["operations"] + sc.operations)
    stale = affected_drafts(db, sc.case_ids, before, after, sc.operations)
    proposer = db.get(User, sc.proposed_by)
    with ledger.transaction(db):
        sc.status, sc.approved_by, sc.decision_reason, sc.decided_at = "applied", user.id, reason, utcnow_iso()
        for s in stale:
            d = db.get(ActionDraft, s["draft_id"])
            d.stale, d.status, d.stale_reason = True, "NEEDS_REAPPROVAL", f"Scenario applied: {s['why']}."
        persist_run(db, user, sc.case_ids, after)
        ledger.append(db, actor=user.username, action="SCENARIO_APPLIED", payload={
            "case_id": sc.case_ids[0], "cases": sc.case_ids, "scenario_id": sc.id, "operations": sc.operations,
            "proposed_by": proposer.username if proposer else None, "approved_by": user.username,
            "reason": reason, "drafts_marked_needs_reapproval": [s["draft_id"] for s in stale]})
    checkpoints.take(db, f"scenario applied ({sc.id})")
    return {**scenario_out(db, sc), "drafts_marked_needs_reapproval": stale}


# --- drafts ---------------------------------------------------------------------------

def draft_out(db: Session, d: ActionDraft) -> dict:
    who = lambda uid: (db.get(User, uid).username if uid else None)  # noqa: E731
    return {"id": d.id, "set_id": d.set_id, "lead_id": d.lead_id, "account_id": d.account_id, "method": d.method,
            "amount": float(d.amount or 0), "estimate_min": float(d.estimate_min or 0),
            "estimate_max": float(d.estimate_max or 0), "as_of": d.as_of, "assumptions": d.assumptions,
            "notes": d.notes, "draft_text": d.draft_text, "status": d.status, "stale": d.stale,
            "stale_reason": d.stale_reason, "case_ids": d.case_ids, "created_by": who(d.created_by),
            "created_at": d.created_at, "approved_by": who(d.approved_by), "approved_at": d.approved_at}


def create_drafts(db: Session, settings: Settings, user: User, lead: Lead, method: str,
                  actor: str | None = None) -> dict:
    inp, result, obs = lead_context(db, settings, lead)
    if obs is None:
        raise Refused("This lead is not produced by the current analysis; re-run analysis first.")
    ds = build_draft_set(obs, result, inp, method, labels_for(inp, result))
    if not ds["within_attributable"]:
        raise Refused("Draft total exceeds the amount attributable under this method.")
    set_id, now = new_id(), utcnow_iso()
    with ledger.transaction(db):
        for old in db.scalars(select(ActionDraft).where(ActionDraft.lead_id == lead.id, ActionDraft.status == "DRAFT")):
            old.status = "SUPERSEDED"
        for x in ds["drafts"]:
            db.add(ActionDraft(lead_id=lead.id, set_id=set_id, account_id=x["account_id"], method=method,
                               amount=x["amount"], estimate_min=x["estimate_min"], estimate_max=x["estimate_max"],
                               as_of=x["as_of"], assumptions=x["assumptions"], notes=x["notes"],
                               inputs_hash=x["inputs_hash"], draft_text=x["draft_text"], case_ids=x["cases"] or ds["case_ids"],
                               sources=x["sources"], status="DRAFT", stale=False, created_by=user.id, created_at=now))
        ledger.append(db, actor=actor or user.username, action="DRAFTS_CREATED", payload={
            "case_id": ds["case_ids"][0] if ds["case_ids"] else lead.case_ids[0], "lead": lead.key, "set_id": set_id,
            "method": method, "drafts": len(ds["drafts"]), "total": ds["total"],
            "attributable_under_method": ds["attributable_under_method"]})
    return {**ds, "set_id": set_id}


def approve_draft(db: Session, user: User, d: ActionDraft, reason: str, actor: str | None = None) -> dict:
    if d.status not in ("DRAFT", "NEEDS_REAPPROVAL"):
        raise Refused(f"A draft in {d.status} cannot be approved.")
    with ledger.transaction(db):
        d.status, d.stale, d.approved_by, d.approved_at = "APPROVED", False, user.id, utcnow_iso()
        ledger.append(db, actor=actor or user.username, action="DRAFT_APPROVED", payload={
            "case_id": (d.case_ids or ["?"])[0], "draft_id": d.id, "account": d.account_id, "method": d.method,
            "amount": float(d.amount or 0), "reason": reason, "note": "Approved for issue by the officer; the system "
                                                                      "sends nothing."})
    checkpoints.take(db, f"draft approval ({d.id})")
    return draft_out(db, d)


# --- export ---------------------------------------------------------------------------

def export_bundle(db: Session, settings: Settings, user: User, lead: Lead) -> dict:
    inp, result, obs = lead_context(db, settings, lead)
    if obs is None:
        raise Refused("This lead is not produced by the current analysis; re-run analysis first.")
    drafts = [draft_out(db, d) for d in db.scalars(select(ActionDraft).where(
        ActionDraft.lead_id == lead.id, ActionDraft.status != "SUPERSEDED").order_by(ActionDraft.created_at))]
    method = drafts[-1]["method"] if drafts else None
    extractors = []
    for f in db.scalars(select(EvidenceFile).where(EvidenceFile.id.in_([f["id"] for f in inp["files"]]))):
        extractors += f.extractor_versions or []
    now = utcnow_iso()
    with ledger.transaction(db):
        snap = Snapshot(case_ids=lead_cases(db, lead), input_hashes={"input": result["input_hash"]},
                        decisions=inp.get("identity_decisions", []), operations=result["operations"],
                        rule_versions=result["rule_versions"], parameters=result["params"], attribution_method=method,
                        software_versions={"engine": result["engine_version"], "pramana": result["software_version"]},
                        expected_results=summary(result), created_at=now)
        db.add(snap)
        db.flush()
        ledger.append(db, actor=user.username, action="LEAD_EXPORTED", payload={
            "case_id": lead.case_ids[0], "lead": lead.key, "snapshot_id": snap.id, "input_hash": result["input_hash"]})
    cp = checkpoints.take(db, f"export ({lead.key})")
    head = db.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    return bundle_mod.build_bundle(
        lead={**lead_out(db, lead), "snapshot_id": snap.id}, inp=inp, result=result, drafts=drafts, method=method,
        ledger_head={"seq": head.seq, "hash": head.hash}, checkpoint=cp, generated_by=user.username,
        generated_at=now, extractor_versions=extractors)


def lead_detail(db: Session, settings: Settings, lead: Lead) -> dict:
    inp, result, obs = lead_context(db, settings, lead)
    drafts = [draft_out(db, d) for d in db.scalars(select(ActionDraft).where(
        ActionDraft.lead_id == lead.id, ActionDraft.status != "SUPERSEDED").order_by(ActionDraft.created_at))]
    scenarios = [scenario_out(db, s) for s in db.scalars(select(Scenario).where(Scenario.lead_id == lead.id)
                                                         .order_by(Scenario.created_at.desc()))]
    history = [{"seq": e.seq, "ts": e.ts, "actor": e.actor, "action": e.action}
               for e in db.scalars(select(LedgerEntry).where(LedgerEntry.payload.contains(f'"{lead.key}"'))
                                   .order_by(LedgerEntry.seq))]
    rec = receipt(obs, inp, result) if obs else None
    srcs = []
    if obs:
        for g in sources_of(result, lead.key):
            srcs.append({**g, "dependents": dependencies(result, g["source"])})
    files = {f["id"]: f["filename"] for f in inp["files"]}
    return {**lead_out(db, lead), "receipt": rec, "reproduced_now": obs is not None, "drafts": drafts,
            "scenarios": scenarios, "history": history, "sources": srcs, "filenames": files,
            "operations_applied": result["operations"]}
