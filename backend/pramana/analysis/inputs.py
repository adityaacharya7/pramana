"""Build the analysis input: a plain, JSON-serialisable snapshot of the
*reviewed* evidence for a set of cases.

Everything the rules, the money trail and MO matching read comes from here,
so the same analysis can run live, on a Challenge Mode copy, or from a
handover bundle on another machine with no database at all. Only confirmed
mentions and the transactions derived from them are included; every item
carries the source group it rests on.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..config import Settings
from ..extraction import engine as xengine
from ..extraction import quality
from ..extraction.identifiers import ACCOUNT, IMEI, PHONE, UPI, WALLET
from ..models import (
    Case, Edge, EdgeSupport, Entity, EntityMention, EvidenceFile, Extraction, IdentityDecision, QualityIssue,
    Scenario, Transaction,
)

INPUT_VERSION = "1"
SHARED_ID_TYPES = {PHONE, ACCOUNT, UPI, IMEI, WALLET}
NARRATIVE_KINDS = {"complaint"}
REF_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def input_hash(inp: dict) -> str:
    return hashlib.sha256(canonical_json(inp).encode("utf-8")).hexdigest()


def applied_operations(db: Session, case_ids: list[str]) -> list[dict]:
    """Operations from Challenge Mode scenarios a supervisor has applied to
    the live case. They are part of the case from then on."""
    ops = []
    for sc in db.scalars(select(Scenario).where(Scenario.status == "applied").order_by(Scenario.decided_at)):
        if set(sc.case_ids or []) & set(case_ids):
            for op in sc.operations or []:
                ops.append({**op, "scenario_id": sc.id})
    return ops


def build_input(db: Session, settings: Settings, case_ids: list[str]) -> dict:
    case_ids = sorted(set(case_ids))
    cases = db.scalars(select(Case).where(Case.id.in_(case_ids)).order_by(Case.id)).all()
    files = {f.id: f for f in db.scalars(select(EvidenceFile).where(EvidenceFile.case_id.in_(case_ids)))}
    file_rows = [{"id": f.id, "case_id": f.case_id, "filename": f.filename, "kind": f.kind, "type": f.type,
                  "sha256": f.sha256, "source_group": f.source_group_id, "integrity": f.integrity_status}
                 for f in sorted(files.values(), key=lambda f: (f.case_id, f.uploaded_at))]
    texts: dict[str, str | None] = {}

    def text_of(f: EvidenceFile) -> str | None:
        if f.id not in texts:
            try:
                texts[f.id] = xengine.evidence_text(settings, f)
            except storage.IntegrityMismatch:
                texts[f.id] = None
        return texts[f.id]

    # --- statement coverage and balances
    statements, seen_groups, own_of_group = [], set(), {}
    for f in files.values():
        if f.type != "CSV" or f.source_group_id in seen_groups or not f.extracted_at:
            continue
        text = text_of(f)
        if text is None:
            continue
        meta = quality.statement_meta(text, f.source_group_id, xengine.date_order_for(db, f))
        if meta is None:
            continue
        seen_groups.add(f.source_group_id)
        own_of_group[f.source_group_id] = meta.account
        statements.append({"file_id": f.id, "case_id": f.case_id, "account": meta.account, "start": meta.start,
                           "end": meta.end, "opening": meta.opening, "closing": meta.closing,
                           "source": f.source_group_id})
    statements.sort(key=lambda s: (s["account"], s["start"]))

    # --- transactions (one row per statement row; byte-identical copies once)
    txns, seen_rows = [], set()
    for t in db.scalars(select(Transaction).where(Transaction.evidence_file_id.in_(list(files) or [""]))
                        .order_by(Transaction.ts, Transaction.id)):
        f = files[t.evidence_file_id]
        row_key = (f.source_group_id, t.row_number)
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)
        txns.append({
            "id": f"{f.source_group_id}:r{t.row_number}", "file_id": f.id, "case_id": f.case_id,
            "row": t.row_number, "span": [t.span_start, t.span_end],
            "from": t.from_acct, "to": t.to_acct, "amount": float(t.amount), "ts": t.ts, "channel": t.channel or "",
            "reference": t.reference or "", "description": t.description or "",
            "counterparty_name": t.counterparty_name or "", "ts_ambiguous": bool(t.ts_ambiguous),
            "own": own_of_group.get(f.source_group_id, ""),
            "source": f"bankref:{t.reference}" if t.reference else f"{f.source_group_id}:r{t.row_number}",
        })

    # --- identifier mentions (for shared identifiers across cases)
    mentions = []
    rows = db.execute(
        select(Entity, Extraction, EntityMention.case_id)
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .join(Extraction, Extraction.id == EntityMention.extraction_id)
        .where(EntityMention.case_id.in_(case_ids), Entity.type.in_(SHARED_ID_TYPES))
    ).all()
    for ent, x, cid in rows:
        f = files.get(x.file_id)
        if f is None:
            continue
        mentions.append({"entity_id": ent.id, "type": ent.type, "value": ent.canonical_value, "case_id": cid,
                         "file_id": f.id, "span": [x.span_start, x.span_end], "source": f.source_group_id,
                         "names_seen": (ent.attrs or {}).get("names_seen", [])})
    mentions.sort(key=lambda m: (m["value"], m["case_id"], m["file_id"], m["span"][0]))

    # --- KYC facts: account-opening details with the rows that state them
    kyc: dict[str, dict] = {}
    kyc_edges = db.execute(
        select(Edge, EdgeSupport, Entity).join(EdgeSupport, EdgeSupport.edge_id == Edge.id)
        .join(Entity, Entity.id == Edge.dst)
        .where(EdgeSupport.evidence_file_id.in_(list(files) or [""]),
               Edge.type.in_(["opened_at", "opened_by", "registered_to", "owns"]))
    ).all()
    ents_cache: dict[str, Entity] = {}

    def ent(eid: str) -> Entity:
        if eid not in ents_cache:
            ents_cache[eid] = db.get(Entity, eid)
        return ents_cache[eid]

    aliases = []
    for edge, sup, dst in kyc_edges:
        f = files[sup.evidence_file_id]
        if f.kind != "kyc_response" and edge.type != "owns":
            continue
        src = ent(edge.src)
        src_rec = {"file_id": f.id, "case_id": f.case_id, "span": [sup.span_start, sup.span_end],
                   "source": sup.source_group_id}
        if edge.type in ("opened_at", "opened_by"):
            k = kyc.setdefault(src.canonical_value, {"account": src.canonical_value, "records": []})
            k["branch" if edge.type == "opened_at" else "official"] = dst.canonical_value
            if edge.type == "opened_by":
                k["official_name"] = (dst.attrs or {}).get("name")
            k.update({key: v for key, v in ((src.attrs or {}).get("kyc") or {}).items()})
            if src_rec not in k["records"]:
                k["records"].append(src_rec)
        elif edge.type == "registered_to" and dst.type == ACCOUNT:
            if src.type == PHONE and f.kind == "kyc_response":
                k = kyc.setdefault(dst.canonical_value, {"account": dst.canonical_value, "records": []})
                k.setdefault("phones", [])
                if src.canonical_value not in k["phones"]:
                    k["phones"].append(src.canonical_value)
            elif src.type == UPI:
                aliases.append({"a": src.canonical_value, "b": dst.canonical_value, **src_rec})
        elif edge.type == "owns" and dst.type == ACCOUNT and f.kind == "kyc_response":
            k = kyc.setdefault(dst.canonical_value, {"account": dst.canonical_value, "records": []})
            holders = k.setdefault("holders", [])
            addr = (src.attrs or {}).get("address")
            h = {"name": src.canonical_value, "type": src.type, "address": addr}
            if h not in holders:
                holders.append(h)
    for k in kyc.values():
        k["records"].sort(key=lambda r: (r["file_id"], r["span"][0]))

    # --- complaints: who complains, which accounts are theirs, which they name
    complaints, trade_records = [], []
    for f in sorted(files.values(), key=lambda f: (f.case_id, f.uploaded_at)):
        if f.type == "CSV" or not f.extracted_at or f.source_group_id != f.id:
            continue
        text = text_of(f)
        if text is None:
            continue
        confirmed = {(x.span_start, x.span_end): x for x in db.scalars(
            select(Extraction).where(Extraction.file_id == f.id, Extraction.status == "CONFIRMED"))}
        if not confirmed:
            continue
        _, parsed = xengine.parse_evidence(db, settings, f)
        conf_mentions = [m for m in parsed.mentions if m.span in confirmed]
        if f.kind in NARRATIVE_KINDS:
            principal = next((m for m in conf_mentions if m.role == "principal"), None)
            own = []
            if principal:
                for r in parsed.relations:
                    if (r.type == "owns" and r.src == principal.span and r.dst in confirmed
                            and r.attrs.get("basis") == "complainant's own account"):
                        m = next(x for x in conf_mentions if x.span == r.dst)
                        own.append({"value": m.value, "span": list(m.span)})
            own_phones = []
            if principal:
                for r in parsed.relations:
                    if r.type == "uses" and r.src == principal.span and r.dst in confirmed:
                        m = next(x for x in conf_mentions if x.span == r.dst)
                        own_phones.append({"value": m.value, "span": list(m.span)})
            own_values = {o["value"] for o in own}
            named = [{"value": m.value, "type": m.type, "span": list(m.span)} for m in conf_mentions
                     if m.type in (ACCOUNT, UPI) and m.value not in own_values]
            phones = [{"value": m.value, "span": list(m.span)} for m in conf_mentions if m.type == PHONE]
            complaints.append({
                "file_id": f.id, "case_id": f.case_id, "filename": f.filename, "text": text,
                "complainant": principal.value if principal else None,
                "complainant_span": list(principal.span) if principal else None,
                "victim_accounts": own, "named_accounts": named, "phones": phones, "complainant_phones": own_phones,
                "source": f.source_group_id,
            })
        wallets = [{"value": m.value, "span": list(m.span)} for m in conf_mentions if m.type == WALLET]
        if wallets:
            refs = [{"reference": m.group(1), "span": [m.start(1), m.end(1)]} for m in REF_RE.finditer(text)]
            trade_records.append({"file_id": f.id, "case_id": f.case_id, "filename": f.filename, "kind": f.kind,
                                  "wallets": wallets, "references": refs, "source": f.source_group_id})

    issues = [{"id": q.id, "case_id": q.case_id, "check": q.check, "file_ids": q.file_ids, "status": q.status,
               "detail": q.detail} for q in db.scalars(select(QualityIssue).where(QualityIssue.case_id.in_(case_ids))
                                                       .order_by(QualityIssue.created_at))]
    decisions = [{"entity_a": d.entity_a, "entity_b": d.entity_b, "decision": d.decision, "reason": d.reason,
                  "decided_at": d.decided_at}
                 for d in db.scalars(select(IdentityDecision).order_by(IdentityDecision.decided_at))]

    return {
        "version": INPUT_VERSION,
        "cases": [{"id": c.id, "fir_no": c.fir_no, "unit": c.unit, "city": c.city, "title": c.title,
                   "station": c.station, "registered_on": c.registered_on, "complainant": c.complainant}
                  for c in cases],
        "files": file_rows,
        "transactions": txns,
        "statements": statements,
        "mentions": mentions,
        "kyc": sorted(kyc.values(), key=lambda k: k["account"]),
        "aliases": aliases,
        "complaints": complaints,
        "trade_records": trade_records,
        "quality_issues": issues,
        "identity_decisions": decisions,
    }
