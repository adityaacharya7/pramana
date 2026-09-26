"""Graph, timeline and click-to-source."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import graph as graphs
from .. import storage
from ..config import Settings
from ..deps import current_user, get_db, get_settings
from ..extraction import engine
from ..extraction.identifiers import DOCUMENT
from ..identity import representatives
from ..models import Edge, EdgeSupport, Entity, EntityMention, EvidenceFile, Extraction, User
from ..permissions import require_case, visible_case_ids
from .evidence import BLOCKED, _mark
from .review import TextCache, snippet

router = APIRouter(tags=["graph"])


@router.get("/cases/{case_id}/graph")
def case_graph(case_id: str, focus: str | None = None, hops: int | None = Query(None, ge=1, le=3),
               documents: bool = True, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = require_case(db, user, case_id, "graph.read")
    return graphs.build_case_graph(db, case.id, visible_case_ids(db, user, "graph.read"), focus, hops, documents)


def _members(db: Session, entity_id: str) -> list[str]:
    reps = representatives(db)
    root = reps.get(entity_id, entity_id)
    return sorted({e for e, r in reps.items() if r == root} | {entity_id, root})


def _focus_values(db: Session, entity_id: str) -> set[str]:
    """Identifier values that belong to an entity (and its merged records):
    the entity itself, plus accounts/phones a person owns or uses."""
    ids = _members(db, entity_id)
    values = {e.canonical_value for e in db.scalars(select(Entity).where(Entity.id.in_(ids)))}
    linked = db.scalars(select(Entity.canonical_value).join(Edge, Edge.dst == Entity.id)
                        .where(Edge.src.in_(ids), Edge.type.in_(["owns", "uses"]))).all()
    return values | set(linked)


@router.get("/cases/{case_id}/timeline")
def case_timeline(case_id: str, focus: str | None = None, user: User = Depends(current_user),
                  db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    case = require_case(db, user, case_id, "graph.read")
    return graphs.timeline(db, settings, case.id, _focus_values(db, focus) if focus else None)


@router.get("/entities/{entity_id}")
def entity_detail(entity_id: str, case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    require_case(db, user, case_id, "graph.read")
    visible = visible_case_ids(db, user, "graph.read")
    ids = _members(db, entity_id)
    ents = db.scalars(select(Entity).where(Entity.id.in_(ids))).all()
    if not ents:
        raise HTTPException(status_code=404, detail="Entity not found.")
    rows = db.execute(
        select(EntityMention, Extraction, EvidenceFile)
        .join(Extraction, Extraction.id == EntityMention.extraction_id)
        .join(EvidenceFile, EvidenceFile.id == Extraction.file_id)
        .where(EntityMention.entity_id.in_(ids), EntityMention.case_id.in_(visible))
        .order_by(EntityMention.case_id, EvidenceFile.uploaded_at, Extraction.span_start)
    ).all()
    doc_files = [db.get(EvidenceFile, (e.attrs or {}).get("evidence_file_id")) for e in ents if e.type == DOCUMENT]
    doc_files = [f for f in doc_files if f and f.case_id in visible]
    if not rows and not doc_files:
        # Exists, but only in cases this user cannot see.
        raise HTTPException(status_code=404, detail="Entity not found.")
    texts = TextCache(db, settings)
    mentions = []
    for m, x, f in rows[:200]:
        text = texts.get(f)
        mentions.append({"extraction_id": x.id, "evidence_id": f.id, "filename": f.filename, "case_id": f.case_id,
                         "kind": f.kind, "span": [x.span_start, x.span_end], "text": x.text,
                         "extractor": x.extractor,
                         "snippet": snippet(text, x.span_start, x.span_end) if text else None})
    root = ents[0] if len(ents) == 1 else min(ents, key=lambda e: e.id)
    return {
        "id": root.id, "type": root.type, "label": root.canonical_value,
        "records": [{"id": e.id, "type": e.type, "value": e.canonical_value, "attrs": e.attrs or {}} for e in ents],
        "cases": sorted({m.case_id for m, _, _ in rows} | {f.case_id for f in doc_files}),
        "mentions": mentions, "mention_total": len(rows),
        "document_file": ({"evidence_id": doc_files[0].id, "filename": doc_files[0].filename}
                          if doc_files else None),
    }


@router.get("/edges/support")
def edge_support(ids: str, case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    """The records behind an edge: file, exact span and surrounding text.
    Only records from cases the user can see are returned."""
    require_case(db, user, case_id, "graph.read")
    visible = set(visible_case_ids(db, user, "graph.read"))
    edge_ids = [i for i in ids.split(",") if i][:50]
    rows = db.execute(
        select(EdgeSupport, Edge, EvidenceFile).join(Edge, Edge.id == EdgeSupport.edge_id)
        .join(EvidenceFile, EvidenceFile.id == EdgeSupport.evidence_file_id)
        .where(EdgeSupport.edge_id.in_(edge_ids)).order_by(EvidenceFile.uploaded_at, EdgeSupport.span_start)
    ).all()
    texts = TextCache(db, settings)
    out, groups = [], set()
    for sup, edge, f in rows:
        if f.case_id not in visible:
            continue
        groups.add(sup.source_group_id)
        text = texts.get(f)
        out.append({"edge_id": edge.id, "type": edge.type, "evidence_id": f.id, "filename": f.filename,
                    "case_id": f.case_id, "kind": f.kind, "span": [sup.span_start, sup.span_end],
                    "source_group": sup.source_group_id, "support_kind": sup.kind,
                    "snippet": snippet(text, sup.span_start, sup.span_end, 40) if text else None})
    if not out:
        raise HTTPException(status_code=404, detail="No visible source for this relationship.")
    return {"supports": out, "independent_sources": len(groups)}


@router.get("/evidence/{evidence_id}/text", response_class=PlainTextResponse)
def evidence_text(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    """The text that extraction spans refer to (for PDFs, the extracted text).
    Re-hashed on every load."""
    ev = db.get(EvidenceFile, evidence_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Evidence file not found.")
    require_case(db, user, ev.case_id, "evidence.read")
    try:
        return PlainTextResponse(engine.evidence_text(settings, ev), headers={"X-Evidence-SHA256": ev.sha256})
    except storage.IntegrityMismatch as e:
        _mark(db, ev, "MISSING" if e.actual is None else "MISMATCH", e.actual, user.username)
        raise HTTPException(status_code=409, detail=BLOCKED)
