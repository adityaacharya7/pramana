"""Identity review (F4).

People and organisations are entities per record. Two records become one
person only when an officer merges them; the system only proposes, and
scores a proposal on identifiers, never on the name alone:

  merge_suggested           similar names, and a phone, account, UPI ID or ID
                            document is shared
  likely_different          similar names, but both records carry phones or ID
                            documents and none match
  insufficient_identifiers  similar names and nothing either way

Decisions are stored, never applied destructively: the graph resolves the
latest decision for each pair when it is built, so SPLIT undoes a MERGE.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .extraction.identifiers import ACCOUNT, NAMED_TYPES, PHONE, UPI
from .extraction.narrative import _compatible
from .models import Edge, Entity, EntityMention, IdentityDecision

LINK_TYPES = {"owns", "uses"}
STRONG = {PHONE, ACCOUNT, UPI}
CONFLICT_TYPES = {PHONE, "id_document"}


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def name_similarity(a: str, b: str) -> float:
    if a.lower() == b.lower():
        return 1.0
    if _compatible(a, b):
        return 0.95
    return round(SequenceMatcher(None, a.lower(), b.lower()).ratio(), 3)


def latest_decisions(db: Session) -> dict[tuple[str, str], IdentityDecision]:
    out: dict[tuple[str, str], IdentityDecision] = {}
    for d in db.scalars(select(IdentityDecision).order_by(IdentityDecision.decided_at)):
        out[pair_key(d.entity_a, d.entity_b)] = d
    return out


def representatives(db: Session) -> dict[str, str]:
    """Union-find over pairs whose latest decision is MERGE."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), d in latest_decisions(db).items():
        if d.decision == "MERGE":
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return {x: find(x) for x in parent}


def _holder_phones(db: Session, entity_ids: list[str]) -> list[tuple[str, str]]:
    """A KYC account holder's registered mobile counts as that holder's phone."""
    owned = db.execute(select(Edge.src, Edge.dst).where(Edge.src.in_(entity_ids), Edge.type == "owns")).all()
    if not owned:
        return []
    accounts = {dst for _, dst in owned}
    reg = db.execute(
        select(Edge.dst, Entity.canonical_value).join(Entity, Entity.id == Edge.src)
        .where(Edge.dst.in_(accounts), Edge.type == "registered_to", Entity.type == PHONE)
    ).all()
    phones_of_account: dict[str, set[str]] = {}
    for acct, phone in reg:
        phones_of_account.setdefault(acct, set()).add(phone)
    return [(src, p) for src, acct in owned for p in phones_of_account.get(acct, ())]


def identifiers_of(db: Session, entity_ids: list[str]) -> dict[str, set[tuple[str, str]]]:
    out: dict[str, set[tuple[str, str]]] = {e: set() for e in entity_ids}
    if not entity_ids:
        return out
    rows = db.execute(
        select(Edge.src, Entity.type, Entity.canonical_value).join(Entity, Entity.id == Edge.dst)
        .where(Edge.src.in_(entity_ids), Edge.type.in_(LINK_TYPES))
    ).all()
    for src, etype, value in rows:
        out[src].add((etype, value))
    for src, value in _holder_phones(db, entity_ids):
        out[src].add((PHONE, value))
    for e in db.scalars(select(Entity).where(Entity.id.in_(entity_ids))):
        for doc in (e.attrs or {}).get("id_documents", []):
            out[e.id].add(("id_document", doc))
    return out


def candidates(db: Session, case_ids: list[str], anchor_case: str | None = None,
               threshold: float = 0.85) -> list[dict]:
    """Candidate pairs among people/organisations mentioned in `case_ids`
    (the caller's visible cases). With `anchor_case`, at least one side must
    be mentioned in that case."""
    mentions = db.execute(
        select(EntityMention.entity_id, EntityMention.case_id).join(Entity, Entity.id == EntityMention.entity_id)
        .where(EntityMention.case_id.in_(case_ids), Entity.type.in_(NAMED_TYPES))
    ).all()
    cases_of: dict[str, set[str]] = {}
    for eid, cid in mentions:
        cases_of.setdefault(eid, set()).add(cid)
    ents = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(list(cases_of))))}
    idents = identifiers_of(db, list(ents))
    decisions = latest_decisions(db)

    out = []
    for a, b in combinations(sorted(ents), 2):
        ea, eb = ents[a], ents[b]
        if anchor_case and anchor_case not in cases_of[a] and anchor_case not in cases_of[b]:
            continue
        if ea.type != eb.type:
            continue
        # A candidate needs similar names. A shared phone or account alone is
        # not identity (co-signatories, a family phone: FX-20); it only
        # strengthens a same-name candidate.
        sim = name_similarity(ea.canonical_value, eb.canonical_value)
        if sim < threshold:
            continue
        shared = sorted((idents[a] & idents[b]) & {i for i in idents[a] if i[0] in STRONG | {"id_document"}})
        conflicts = []
        for t in sorted(CONFLICT_TYPES):
            va = sorted(v for k, v in idents[a] if k == t)
            vb = sorted(v for k, v in idents[b] if k == t)
            if va and vb and not set(va) & set(vb):
                conflicts.append({"type": t, "a": va, "b": vb})
        if shared:
            suggestion = "merge_suggested"
        elif conflicts:
            suggestion = "likely_different"
        else:
            suggestion = "insufficient_identifiers"
        d = decisions.get(pair_key(a, b))
        out.append({
            "id": f"{a}:{b}", "a": a, "b": b, "name_similarity": sim,
            "shared": [{"type": t, "value": v} for t, v in shared],
            "conflicting": conflicts, "suggestion": suggestion,
            "identifiers": {a: sorted(idents[a]), b: sorted(idents[b])},
            "decision": None if d is None else {
                "decision": d.decision, "reason": d.reason, "user_id": d.user_id, "decided_at": d.decided_at},
        })
    order = {"merge_suggested": 0, "likely_different": 1, "insufficient_identifiers": 2}
    out.sort(key=lambda c: (c["decision"] is not None, order[c["suggestion"]], -c["name_similarity"]))
    return out
