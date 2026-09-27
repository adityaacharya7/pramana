"""The financial model the rules and the money trail work on.

* A **party** is one holder of money, whatever it is called: an account
  number and the UPI ID that pays into it are one party once a bank record
  or a KYC response ties them together.
* An **event** is one movement of money. Both statements of an IMPS transfer
  carry the same bank reference, so they are one event with two supporting
  rows (and one source group), never two transfers.

Challenge Mode operations are applied here, before anything is computed:
  exclude_source   drop every record of a source group
  simulate_no_txn  drop one event (a counterfactual)
  dispute_txn      keep the event, flagged, so results can be shown with
                   and without it
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

SPECIAL = {"CASH", "BANK_CHARGES", "UNKNOWN"}


def is_special(v: str) -> bool:
    return v in SPECIAL or v.upper().startswith(("SYNATM", "ATM"))


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


class Parties:
    """Union-find over identifiers, preferring a bank account number as the
    name of the merged party."""

    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    @staticmethod
    def _better(a: str, b: str) -> str:
        ka = (not a.isdigit(), a)
        kb = (not b.isdigit(), b)
        return a if ka <= kb else b

    def union(self, a: str, b: str) -> None:
        if not a or not b or is_special(a) or is_special(b):
            return
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        keep = self._better(ra, rb)
        drop = rb if keep == ra else ra
        self.parent[drop] = keep

    def rep(self, x: str) -> str:
        return x if is_special(x) else self.find(x)


@dataclass
class Event:
    id: str
    ts: str
    dt: datetime
    amount: float
    src: str
    dst: str
    channel: str
    reference: str
    description: str
    names: list[str]
    rows: list[dict]  # transaction rows (with file, span, source)
    sources: set[str]
    cases: set[str]
    ambiguous: bool = False
    disputed: bool = False


@dataclass
class Model:
    parties: Parties
    events: list[Event]
    statements: dict[str, dict]  # party -> {start, end, opening, closing, files: [...], periods: [...]}
    complaints: list[dict]  # with "victims" and "named" as party ids
    victim_parties: set[str]
    complaint_linked: set[str]
    kyc: dict[str, dict]  # party -> facts
    trade_links: dict[str, list[dict]]  # bank reference -> trade records naming it
    mentions: list[dict]
    names: dict[str, list[str]]  # party -> names seen on statements
    operations: list[dict]
    excluded_sources: set[str] = field(default_factory=set)

    def seed_case(self, e: Event) -> str | None:
        """The complaint case in which this event is a victim's payment."""
        for c in self.complaints:
            if e.src in c["victims"] and e.dst in c["named"]:
                return c["case_id"]
        return None


def build_model(inp: dict, operations: list[dict] | None = None) -> Model:
    ops = list(operations or [])
    excluded = {o["source"] for o in ops if o.get("op") == "exclude_source"}
    removed = {o["event_id"] for o in ops if o.get("op") == "simulate_no_txn"}
    disputed = {o["event_id"] for o in ops if o.get("op") == "dispute_txn"}

    txns = [t for t in inp["transactions"] if t["source"] not in excluded]
    parties = Parties()

    groups: dict[str, list[dict]] = defaultdict(list)
    for t in txns:
        groups[f"ref:{t['reference']}" if t["reference"] else f"row:{t['id']}"].append(t)

    # Two views of one transfer name the same payer and the same payee.
    for rows in groups.values():
        froms = [t["from"] for t in rows]
        tos = [t["to"] for t in rows]
        for a, b in zip(froms, froms[1:]):
            parties.union(a, b)
        for a, b in zip(tos, tos[1:]):
            parties.union(a, b)
    for al in inp.get("aliases", []):
        if al["source"] not in excluded:
            parties.union(al["a"], al["b"])
    for t in txns:  # register every identifier
        for v in (t["from"], t["to"]):
            if not is_special(v):
                parties.find(v)

    rep = parties.rep
    names: dict[str, set[str]] = defaultdict(set)
    events: list[Event] = []
    for eid, rows in groups.items():
        if eid in removed:
            continue
        first = min(rows, key=lambda t: t["ts"])
        e = Event(
            id=eid, ts=first["ts"], dt=parse_ts(first["ts"]), amount=round(first["amount"], 2),
            src=rep(first["from"]), dst=rep(first["to"]), channel=first["channel"], reference=first["reference"],
            description=first["description"], names=sorted({t["counterparty_name"] for t in rows if t["counterparty_name"]}),
            rows=[{"id": t["id"], "file_id": t["file_id"], "case_id": t["case_id"], "span": t["span"], "row": t["row"],
                   "source": t["source"]} for t in rows],
            sources={t["source"] for t in rows}, cases={t["case_id"] for t in rows},
            ambiguous=any(t["ts_ambiguous"] for t in rows), disputed=eid in disputed,
        )
        events.append(e)
    events.sort(key=lambda e: (e.dt, e.id))

    # The name a statement shows belongs to the row's counterparty: the side
    # that is not the statement's own account.
    for t in txns:
        if t["counterparty_name"]:
            cp = t["from"] if t["to"] == t["own"] else t["to"]
            names[rep(cp)].add(t["counterparty_name"])

    statements: dict[str, dict] = {}
    for s in inp["statements"]:
        if s["source"] in excluded:
            continue
        p = rep(s["account"])
        st = statements.setdefault(p, {"periods": [], "files": []})
        st["periods"].append({"start": s["start"], "end": s["end"], "opening": s["opening"], "closing": s["closing"],
                              "file_id": s["file_id"], "source": s["source"]})
        st["files"].append(s["file_id"])
    for st in statements.values():
        st["periods"].sort(key=lambda x: x["start"])
        st["start"], st["opening"] = st["periods"][0]["start"], st["periods"][0]["opening"]
        st["end"], st["closing"] = st["periods"][-1]["end"], st["periods"][-1]["closing"]

    complaints, victims, linked = [], set(), set()
    for c in inp["complaints"]:
        if c["source"] in excluded:
            continue
        vic = {rep(v["value"]) for v in c["victim_accounts"]}
        named = {rep(n["value"]) for n in c["named_accounts"]} - vic
        complaints.append({**c, "victims": vic, "named": named})
        victims |= vic
        linked |= vic | named

    kyc: dict[str, dict] = {}
    for k in inp["kyc"]:
        recs = [r for r in k["records"] if r["source"] not in excluded]
        if not recs:
            continue
        kyc[rep(k["account"])] = {**k, "records": recs}

    trade_links: dict[str, list[dict]] = defaultdict(list)
    for tr in inp["trade_records"]:
        if tr["source"] in excluded:
            continue
        for ref in tr["references"]:
            trade_links[ref["reference"]].append({**tr, "reference_span": ref["span"]})

    mentions = [m for m in inp["mentions"] if m["source"] not in excluded]
    return Model(parties=parties, events=events, statements=statements, complaints=complaints,
                 victim_parties=victims, complaint_linked=linked, kyc=kyc, trade_links=dict(trade_links),
                 mentions=mentions, names={k: sorted(v) for k, v in names.items()}, operations=ops,
                 excluded_sources=excluded)
