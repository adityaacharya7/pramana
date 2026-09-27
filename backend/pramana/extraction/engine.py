"""Extraction workflow on the database.

    run_extraction   evidence -> PENDING extractions (+ intake quality issues)
    decide           officer confirms / rejects; confirmed mentions get entities
    derive_file      rebuild one file's edges, edge support and transactions
                     from its confirmed mentions only

Nothing reaches `edges` or `transactions` unless every mention it rests on
has been confirmed, and every edge support row names its file and span.
"""
from __future__ import annotations

import io
from collections import Counter
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import storage
from ..config import Settings
from ..db import utcnow_iso
from ..models import (
    Edge, EdgeSupport, Entity, EntityMention, EvidenceFile, Extraction, QualityIssue, Transaction,
)
from . import parse_file, quality
from .identifiers import DOCUMENT, ID_DOCUMENT, NAMED_TYPES
from .narrative import _compatible
from .types import Parsed

DETERMINISTIC = ("regex-v1", "pattern-v1", "csv-v1")


class Blocked(RuntimeError):
    pass


def evidence_text(settings: Settings, ev: EvidenceFile) -> str:
    """The text spans refer to. Re-hashed on every load; a mismatch blocks."""
    data = storage.read_verified(settings, ev.storage_path, ev.sha256)
    if ev.type == "PDF":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8")


def date_order_for(db: Session, ev: EvidenceFile) -> str:
    issue = db.scalar(select(QualityIssue).where(QualityIssue.check == quality.AMBIGUOUS,
                                                 QualityIssue.issue_key == ev.id))
    if issue and issue.status == "ACKNOWLEDGED" and issue.resolution:
        return issue.resolution.get("date_order", "DMY")
    return "DMY"


_PARSE_CACHE: dict[tuple, Parsed] = {}
_PARSE_CACHE_MAX = 512


def parse_evidence(db: Session, settings: Settings, ev: EvidenceFile) -> tuple[str, Parsed]:
    # The text is re-read and re-hashed on every call (a mismatch raises
    # before anything is used). Parsing is deterministic in (content hash,
    # type, source group, date reading), so that result is cached.
    text = evidence_text(settings, ev)
    order = date_order_for(db, ev)
    key = (ev.sha256, ev.type, ev.source_group_id, order)
    parsed = _PARSE_CACHE.get(key)
    if parsed is None:
        parsed = parse_file(text, ev.type, ev.source_group_id, order)
        if len(_PARSE_CACHE) >= _PARSE_CACHE_MAX:
            _PARSE_CACHE.pop(next(iter(_PARSE_CACHE)))
        _PARSE_CACHE[key] = parsed
    return text, parsed


# --- extraction ------------------------------------------------------------------

def run_extraction(db: Session, settings: Settings, case_id: str, file_ids: Iterable[str] | None = None) -> dict:
    q = select(EvidenceFile).where(EvidenceFile.case_id == case_id)
    if file_ids:
        q = q.where(EvidenceFile.id.in_(list(file_ids)))
    else:
        q = q.where(EvidenceFile.extracted_at.is_(None))
    files = db.scalars(q.order_by(EvidenceFile.uploaded_at)).all()
    created, by_type, blocked, processed = 0, Counter(), [], []
    for ev in files:
        if ev.extracted_at is not None:
            continue  # extraction is run once per file; decisions build on it
        try:
            _, parsed = parse_evidence(db, settings, ev)
        except storage.IntegrityMismatch:
            ev.integrity_status = "MISMATCH"
            blocked.append(ev.filename)
            continue
        except (UnicodeDecodeError, ValueError) as e:
            blocked.append(f"{ev.filename} ({e})")
            continue
        for m in parsed.mentions:
            db.add(Extraction(file_id=ev.id, span_start=m.start, span_end=m.end, text=m.text,
                              entity_type=m.type, proposed_value=m.value, extractor=m.extractor,
                              record_key=m.record_key, status="PENDING"))
            by_type[m.type] += 1
            created += 1
        ev.extracted_at = utcnow_iso()
        ev.extractor_versions = parsed.extractors
        processed.append(ev.filename)
    db.flush()
    issues = run_quality_checks(db, settings, case_id)
    return {"files_processed": processed, "files_blocked": blocked, "extractions_created": created,
            "by_type": dict(by_type), "quality_issues_open": issues}


def run_quality_checks(db: Session, settings: Settings, case_id: str) -> int:
    metas = []
    for ev in db.scalars(select(EvidenceFile).where(EvidenceFile.case_id == case_id, EvidenceFile.type == "CSV")):
        try:
            text = evidence_text(settings, ev)
        except storage.IntegrityMismatch:
            continue
        meta = quality.statement_meta(text, ev.source_group_id, date_order_for(db, ev))
        if meta:
            metas.append((ev, meta))
    now = utcnow_iso()
    for issue in quality.check(metas):
        row = db.scalar(select(QualityIssue).where(QualityIssue.case_id == case_id,
                                                   QualityIssue.check == issue["check"],
                                                   QualityIssue.issue_key == issue["key"]))
        if row is None:
            db.add(QualityIssue(case_id=case_id, check=issue["check"], issue_key=issue["key"],
                                file_ids=issue["file_ids"], detail=issue["detail"], created_at=now))
        else:
            row.file_ids, row.detail = issue["file_ids"], issue["detail"]
    db.flush()
    return len(db.scalars(select(QualityIssue.id).where(QualityIssue.case_id == case_id,
                                                        QualityIssue.status == "OPEN")).all())


# --- decisions -------------------------------------------------------------------

def _entity_for(db: Session, ext: Extraction) -> Entity | None:
    if ext.entity_type == ID_DOCUMENT:
        return None  # kept as an attribute of the person in the same record
    value = ext.proposed_value or ext.text
    if ext.entity_type in NAMED_TYPES:
        # People are identified within their record only. The same name in
        # another record is a different entity until an officer merges them.
        same_record = db.scalars(select(Entity).where(Entity.type == ext.entity_type,
                                                      Entity.scope_key == ext.record_key)).all()
        for e in same_record:
            if e.canonical_value == value or _compatible(e.canonical_value, value):
                if len(value) > len(e.canonical_value):
                    e.attrs = {**(e.attrs or {}), "also_written": sorted({*e.attrs.get("also_written", []),
                                                                         e.canonical_value})}
                    e.canonical_value = value
                return e
        scope = ext.record_key
    else:
        scope = ""
    ent = db.scalar(select(Entity).where(Entity.type == ext.entity_type, Entity.canonical_value == value,
                                         Entity.scope_key == scope))
    if ent is None:
        ent = Entity(type=ext.entity_type, canonical_value=value, scope_key=scope, attrs={}, created_at=utcnow_iso())
        db.add(ent)
        db.flush()
    return ent


def targets_for(db: Session, ext: Extraction, scope: str, types: list[str] | None = None,
                extractors: list[str] | None = None) -> list[Extraction]:
    if scope == "mention":
        return [ext]
    q = select(Extraction).where(Extraction.file_id == ext.file_id, Extraction.status == "PENDING")
    if scope == "value":
        q = q.where(Extraction.entity_type == ext.entity_type, Extraction.proposed_value == ext.proposed_value)
    elif scope != "file":
        raise ValueError(f"unknown scope {scope!r}")
    if types:
        q = q.where(Extraction.entity_type.in_(types))
    if extractors:
        q = q.where(Extraction.extractor.in_(extractors))
    rows = db.scalars(q).all()
    return rows if ext in rows or scope == "file" else [ext, *rows]


def decide(db: Session, user_id: str, case_id: str, targets: list[Extraction], decision: str) -> None:
    now = utcnow_iso()
    for ext in targets:
        existing = db.scalars(select(EntityMention).where(EntityMention.extraction_id == ext.id)).all()
        ext.status, ext.decided_by, ext.decided_at = decision, user_id, now
        if decision == "CONFIRMED":
            if not existing:
                ent = _entity_for(db, ext)
                if ent is not None:
                    db.add(EntityMention(entity_id=ent.id, extraction_id=ext.id, case_id=case_id))
        else:
            for m in existing:
                db.delete(m)
    db.flush()


# --- derivation ------------------------------------------------------------------

def _merge_attrs(ent: Entity, attrs: dict) -> None:
    cur = dict(ent.attrs or {})
    for k, v in attrs.items():
        if isinstance(v, list):
            cur[k] = sorted({*cur.get(k, []), *v})
        elif isinstance(v, dict):
            cur[k] = {**cur.get(k, {}), **v}
        elif v not in (None, ""):
            cur[k] = v
    ent.attrs = cur


def _document_entity(db: Session, ev: EvidenceFile) -> Entity:
    ent = db.scalar(select(Entity).where(Entity.type == DOCUMENT, Entity.scope_key == ev.source_group_id))
    if ent is None:
        ent = Entity(type=DOCUMENT, canonical_value=ev.filename, scope_key=ev.source_group_id,
                     attrs={"evidence_file_id": ev.id, "kind": ev.kind}, created_at=utcnow_iso())
        db.add(ent)
        db.flush()
    return ent


def _upsert_edge(db: Session, src: str, dst: str, etype: str, cache: dict) -> Edge:
    key = (src, dst, etype)
    if key in cache:
        return cache[key]
    edge = db.scalar(select(Edge).where(Edge.src == src, Edge.dst == dst, Edge.type == etype))
    if edge is None:
        edge = Edge(src=src, dst=dst, type=etype, status="ACTIVE")
        db.add(edge)
        db.flush()
    cache[key] = edge
    return edge


def _counterparty_key(raw: str, channel: str, description: str) -> str:
    raw = raw.strip()
    if raw:
        return raw.lower() if "@" in raw else raw
    if channel == "CASH" or "CASH" in description.upper():
        return "CASH"
    if channel == "CHARGES":
        return "BANK_CHARGES"
    return "UNKNOWN"


def derive_file(db: Session, settings: Settings, ev: EvidenceFile) -> dict:
    db.execute(delete(EdgeSupport).where(EdgeSupport.evidence_file_id == ev.id))
    db.execute(delete(Transaction).where(Transaction.evidence_file_id == ev.id))
    try:
        text, parsed = parse_evidence(db, settings, ev)
    except storage.IntegrityMismatch:
        _gc_edges(db)
        return {"blocked": True}

    rows = db.execute(
        select(Extraction, EntityMention.entity_id)
        .outerjoin(EntityMention, EntityMention.extraction_id == Extraction.id)
        .where(Extraction.file_id == ev.id, Extraction.status == "CONFIRMED")
    ).all()
    by_span: dict[tuple[int, int], str] = {}
    id_docs: dict[tuple[int, int], str] = {}
    for ext, entity_id in rows:
        if ext.entity_type == ID_DOCUMENT:
            id_docs[(ext.span_start, ext.span_end)] = ext.proposed_value or ext.text
        elif entity_id:
            by_span[(ext.span_start, ext.span_end)] = entity_id

    cache: dict = {}
    edges_made = 0

    def support(edge: Edge, span: tuple[int, int], group: str) -> None:
        dup = db.scalar(select(EdgeSupport.id).where(EdgeSupport.edge_id == edge.id,
                                                     EdgeSupport.source_group_id == group).limit(1))
        db.add(EdgeSupport(edge_id=edge.id, evidence_file_id=ev.id, span_start=span[0], span_end=span[1],
                           source_group_id=group, kind="duplicate_copy" if dup else "independent"))
        db.flush()

    for rel in parsed.relations:
        src = by_span.get(rel.src)
        if rel.type == "attr:id_document":
            doc = id_docs.get(rel.dst)
            if src and doc:
                _merge_attrs(db.get(Entity, src), {"id_documents": [f"{rel.attrs.get('kind', 'ID')}: {doc}"]})
            continue
        dst = by_span.get(rel.dst)
        if not src or not dst or src == dst:
            continue
        support(_upsert_edge(db, src, dst, rel.type, cache), rel.support, rel.group)
        edges_made += 1

    for upd in parsed.attrs:
        target = by_span.get(upd.target)
        if target:
            _merge_attrs(db.get(Entity, target), upd.attrs)

    own_confirmed = {span for span in by_span}
    txns = 0
    for t in parsed.txns:
        if t.own_span not in own_confirmed:
            continue
        own = db.get(Entity, by_span[t.own_span]).canonical_value
        cp_entity = by_span.get(t.counterparty_span) if t.counterparty_span else None
        cp = db.get(Entity, cp_entity).canonical_value if cp_entity else _counterparty_key(
            t.counterparty_raw, t.channel, t.description)
        src, dst = (cp, own) if t.direction == "in" else (own, cp)
        db.add(Transaction(from_acct=src, to_acct=dst, amount=round(t.amount, 2), ts=t.ts, channel=t.channel,
                           reference=t.reference or None, evidence_file_id=ev.id, row_number=t.row_number,
                           span_start=t.span[0], span_end=t.span[1], description=t.description[:255],
                           counterparty_name=t.counterparty_name[:255] or None, ts_ambiguous=t.ts_ambiguous))
        txns += 1

    if parsed.schema == "narrative" and by_span:
        doc = _document_entity(db, ev)
        for ext, entity_id in rows:
            if entity_id and entity_id != doc.id:
                support(_upsert_edge(db, entity_id, doc.id, "appears_in", cache),
                        (ext.span_start, ext.span_end), ev.source_group_id)
    _gc_edges(db)
    return {"edges_supported": edges_made, "transactions": txns}


def _gc_edges(db: Session) -> None:
    """An edge with no remaining support has no source, so it goes."""
    db.flush()
    db.execute(delete(Edge).where(~Edge.id.in_(select(EdgeSupport.edge_id))))
    db.flush()
