"""Investigation graph and timeline (F5).

Rebuilt in memory from confirmed rows on every request (spec, "Architecture"):
entities with a confirmed mention in the case, and edges with at least one
support row from the case's evidence. Identity merges are applied here, not
written into the data, so they stay reversible.
"""
from __future__ import annotations

from collections import defaultdict

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .extraction.identifiers import DOCUMENT
from .identity import representatives
from .models import Edge, EdgeSupport, Entity, EntityMention, EvidenceFile, Transaction

MAX_NODES = 600


def build_case_graph(db: Session, case_id: str, visible_cases: list[str], focus: str | None = None,
                     hops: int | None = None, documents: bool = True) -> dict:
    files = {f.id: f for f in db.scalars(select(EvidenceFile).where(EvidenceFile.case_id == case_id))}
    reps = representatives(db)
    rep = lambda e: reps.get(e, e)  # noqa: E731

    supports = db.execute(
        select(EdgeSupport, Edge).join(Edge, Edge.id == EdgeSupport.edge_id)
        .where(EdgeSupport.evidence_file_id.in_(list(files) or [""]))
    ).all()
    mentioned = set(db.scalars(select(EntityMention.entity_id).where(EntityMention.case_id == case_id)))

    agg: dict[tuple[str, str, str], dict] = {}
    for sup, edge in supports:
        if edge.type == "appears_in" and not documents:
            continue
        s, d = rep(edge.src), rep(edge.dst)
        if s == d:
            continue
        a = agg.setdefault((s, d, edge.type), {"edge_ids": set(), "groups": set(), "supports": 0})
        a["edge_ids"].add(edge.id)
        a["groups"].add(sup.source_group_id)
        a["supports"] += 1

    node_ids = {rep(e) for e in mentioned}
    for s, d, _ in agg:
        node_ids.update((s, d))
    if not documents:
        node_ids = {n for n in node_ids if n}
    ents = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(list(node_ids) or [""])))}
    if not documents:
        node_ids = {n for n in node_ids if ents.get(n) and ents[n].type != DOCUMENT}

    G = nx.MultiDiGraph()
    G.add_nodes_from(node_ids)
    for (s, d, t), a in agg.items():
        if s in node_ids and d in node_ids:
            G.add_edge(s, d, key=t)

    focus_rep = rep(focus) if focus else None
    if focus_rep and focus_rep in G:
        h = max(1, min(3, hops or 1))
        keep = set(nx.single_source_shortest_path_length(G.to_undirected(as_view=True), focus_rep, cutoff=h))
    else:
        focus_rep = None
        keep = set(G.nodes)
    truncated = len(keep) > MAX_NODES
    if truncated:
        keep = set(sorted(keep, key=lambda n: -G.degree(n))[:MAX_NODES])

    members: dict[str, list[str]] = defaultdict(list)
    for e, r in reps.items():
        members[r].append(e)

    # Where else each node is mentioned, among cases this user may see.
    all_members = {m for n in keep for m in (members.get(n) or [n])}
    other_cases: dict[str, set[str]] = defaultdict(set)
    for eid, cid in db.execute(select(EntityMention.entity_id, EntityMention.case_id)
                               .where(EntityMention.entity_id.in_(list(all_members) or [""]),
                                      EntityMention.case_id.in_(visible_cases))):
        if cid != case_id:
            other_cases[rep(eid)].add(cid)
    mention_counts: dict[str, int] = defaultdict(int)
    for eid in db.scalars(select(EntityMention.entity_id).where(EntityMention.case_id == case_id)):
        mention_counts[rep(eid)] += 1

    def label(e: Entity) -> str:
        return e.canonical_value

    nodes = []
    for n in keep:
        e = ents.get(n)
        if e is None:
            continue
        merged = [m for m in members.get(n, []) if m != n]
        nodes.append({
            "id": n, "type": e.type, "label": label(e), "attrs": e.attrs or {},
            "merged_ids": merged, "mentions": mention_counts.get(n, 0),
            "other_cases": sorted(other_cases.get(n, set())),
        })
    edges = []
    for (s, d, t), a in agg.items():
        if s in keep and d in keep:
            edges.append({"id": f"{s}>{d}:{t}", "source": s, "target": d, "type": t,
                          "edge_ids": sorted(a["edge_ids"]), "independent_sources": len(a["groups"]),
                          "supports": a["supports"]})
    return {"case_id": case_id, "focus": focus_rep, "hops": hops if focus_rep else None,
            "nodes": nodes, "edges": edges, "truncated": truncated}


def timeline(db: Session, settings, case_id: str, focus_values: set[str] | None = None) -> list[dict]:
    """Transfers from confirmed statement rows, one event per bank reference
    (both statements of a transfer are one event with two sources), and calls
    from confirmed CDR rows."""
    from . import storage
    from .extraction.engine import parse_evidence
    from .models import Extraction
    files = {f.id: f for f in db.scalars(select(EvidenceFile).where(EvidenceFile.case_id == case_id))}
    events: dict[str, dict] = {}
    for t in db.scalars(select(Transaction).where(Transaction.evidence_file_id.in_(list(files) or [""]))):
        if focus_values and t.from_acct not in focus_values and t.to_acct not in focus_values:
            continue
        key = f"ref:{t.reference}" if t.reference else f"row:{t.id}"
        ev = events.setdefault(key, {
            "id": key, "ts": t.ts, "kind": "cash" if t.to_acct in ("CASH",) or (t.channel or "") in ("ATM", "CASH")
            else "charge" if t.to_acct == "BANK_CHARGES" else "transfer",
            "from": t.from_acct, "to": t.to_acct, "amount": float(t.amount), "channel": t.channel,
            "reference": t.reference, "description": t.description, "ts_ambiguous": t.ts_ambiguous,
            "names": [], "sources": [],
        })
        if t.counterparty_name and t.counterparty_name not in ev["names"]:
            ev["names"].append(t.counterparty_name)
        ev["sources"].append({"evidence_id": t.evidence_file_id, "filename": files[t.evidence_file_id].filename,
                              "span": [t.span_start, t.span_end], "row": t.row_number})

    for f in files.values():
        if f.type != "CSV" or not f.extracted_at:
            continue
        confirmed = {(x.span_start, x.span_end): x.proposed_value for x in db.scalars(
            select(Extraction).where(Extraction.file_id == f.id, Extraction.status == "CONFIRMED"))}
        if not confirmed:
            continue
        try:
            _, parsed = parse_evidence(db, settings, f)
        except storage.IntegrityMismatch:
            continue
        for c in parsed.calls:
            a, b = confirmed.get(c.a), confirmed.get(c.b)
            if not a or not b or (focus_values and a not in focus_values and b not in focus_values):
                continue
            key = f"call:{f.id}:{c.span[0]}"
            events[key] = {"id": key, "ts": c.ts, "kind": "sms" if c.kind.startswith("SMS") else "call",
                           "from": a, "to": b, "amount": None, "channel": c.kind, "reference": None,
                           "description": f"{c.kind} {c.duration}s" if c.duration else c.kind,
                           "ts_ambiguous": False, "names": [],
                           "sources": [{"evidence_id": f.id, "filename": f.filename, "span": list(c.span), "row": None}]}
    return sorted(events.values(), key=lambda e: e["ts"])
