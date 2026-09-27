"""Money Trail Engine (F8).

Victims' payments are traced forward through the accounts whose statements
are in evidence, under a stated attribution method:

  fifo     outgoing money is taken from the oldest funds in the account first
  lifo     from the newest funds first
  prorata  from every source in proportion to what the account holds

Guarantees (spec, "Amount attribution model"):
* every victim rupee sits at exactly one place at the end - an account
  (estimated holding "as of" its statement end date), an exit point, or an
  account whose statement is missing (onward movement unknown);
* totals never exceed what the victims lost;
* where the records do not reconcile (money leaves an account that, on the
  evidence, did not hold it; or a computed balance disagrees with the
  stated closing balance), the affected figures are marked uncertain instead
  of being given as precise amounts.

The spread across methods is a range across the chosen models, not a
confidence interval or a legal minimum or maximum.
"""
from __future__ import annotations

from collections import defaultdict

from .model import Event, Model, is_special

METHODS = ("fifo", "lifo", "prorata")
METHOD_TEXT = {
    "fifo": "First in, first out: money leaving an account is taken from the oldest funds it holds.",
    "lifo": "Last in, first out: money leaving an account is taken from the most recent funds it received.",
    "prorata": "Pro-rata: money leaving an account is taken from every source in proportion to its share of the balance.",
}
EPS = 0.005


def _victim(tag: str) -> bool:
    return tag.startswith("V:")


def _take(pool: list[list], amount: float, method: str) -> tuple[dict[str, tuple[float, int]], float]:
    """Remove `amount` from `pool` (lots of [tag, amount, ts, layer]).
    Returns ({tag: (amount, max layer)}, shortfall)."""
    got: dict[str, list] = {}
    need = amount
    if method == "prorata":
        total = sum(l[1] for l in pool)
        if total <= EPS:
            return {}, amount
        factor = min(1.0, amount / total)
        for lot in pool:
            part = lot[1] * factor
            if part > 0:
                g = got.setdefault(lot[0], [0.0, 0])
                g[0] += part
                g[1] = max(g[1], lot[3])
                lot[1] -= part
        need = max(0.0, amount - total)
    else:
        order = range(len(pool)) if method == "fifo" else range(len(pool) - 1, -1, -1)
        for i in order:
            if need <= EPS:
                break
            lot = pool[i]
            part = min(lot[1], need)
            if part > 0:
                g = got.setdefault(lot[0], [0.0, 0])
                g[0] += part
                g[1] = max(g[1], lot[3])
                lot[1] -= part
                need -= part
    pool[:] = [l for l in pool if l[1] > EPS]
    return {t: (round(a, 6), l) for t, (a, l) in ((k, v) for k, v in got.items())}, (need if need > EPS else 0.0)


def exit_kind(model: Model, e: Event) -> str | None:
    # Direction decides, not the channel: a cash *deposit* is money in.
    if e.dst == "BANK_CHARGES":
        return "bank charges"
    if is_special(e.dst):
        return "cash withdrawal"
    if e.reference and e.reference in model.trade_links:
        return "crypto conversion (trade record)"
    if e.channel == "UPI-P2M" and e.dst not in model.statements:
        return "merchant payment"
    return None


def run(model: Model, method: str, skip_events: set[str] | None = None) -> dict:
    if method not in METHODS:
        raise ValueError(method)
    skip = skip_events or set()
    pools: dict[str, list[list]] = {}
    for party, st in model.statements.items():
        if party in model.victim_parties:
            continue
        pools[party] = [["other:opening balance", st["opening"], st["start"], 0]] if st["opening"] > EPS else []
    arrivals: dict[str, dict[str, list]] = defaultdict(dict)  # party without statement -> tag -> [amount, layer, first ts]
    seeds, flows, exits, issues = [], [], [], []
    first_traced_in: dict[str, str] = {}

    for e in model.events:
        if e.id in skip:
            continue
        case = model.seed_case(e)
        if case:
            tag = f"V:{case}:{e.src}"
            portions = {tag: (e.amount, 0)}
            seeds.append({"event": e.id, "case_id": case, "victim": e.src, "to": e.dst, "amount": e.amount,
                          "ts": e.ts, "sources": sorted(e.sources)})
        elif e.src in pools:
            portions, short = _take(pools[e.src], e.amount, method)
            if short > EPS:
                portions["unexplained"] = (short, 0)
                issues.append({"party": e.src, "event": e.id, "ts": e.ts, "kind": "outflow_exceeds_known_funds",
                               "amount": round(short, 2),
                               "detail": "Money left this account that, on the records available, it did not hold."})
        else:
            portions = {"other": (e.amount, 0)}

        kind = exit_kind(model, e)
        for tag, (amt, layer) in portions.items():
            if not _victim(tag) or amt <= EPS:
                continue
            flows.append({"event": e.id, "from": e.src, "to": e.dst, "tag": tag, "amount": round(amt, 2),
                          "layer": layer + 1, "ts": e.ts, "exit": kind})
            if kind:
                exits.append({"event": e.id, "party": e.src, "to": e.dst, "tag": tag, "amount": round(amt, 2),
                              "kind": kind, "ts": e.ts, "layer": layer + 1,
                              "trade_records": [t["file_id"] for t in model.trade_links.get(e.reference, [])]})
            elif e.dst not in model.victim_parties:
                first_traced_in.setdefault(e.dst, e.ts)
        if kind:
            continue
        if e.dst in pools:
            pools[e.dst].extend([[t, a, e.ts, l + 1] for t, (a, l) in portions.items() if a > EPS])
        elif e.dst not in model.victim_parties and not is_special(e.dst):
            for tag, (amt, layer) in portions.items():
                if _victim(tag) and amt > EPS:
                    a = arrivals[e.dst].setdefault(tag, [0.0, layer + 1, e.ts])
                    a[0] += amt
                    a[1] = max(a[1], layer + 1)

    holdings = []
    for party, pool in pools.items():
        st = model.statements[party]
        balance = sum(l[1] for l in pool)
        stated = st["closing"]
        reconciles = abs(balance - stated) <= 0.5
        if not reconciles:
            issues.append({"party": party, "kind": "closing_balance_mismatch", "computed": round(balance, 2),
                           "stated": stated, "detail": "Computed balance differs from the stated closing balance."})
        by_tag: dict[str, list] = {}
        for tag, amt, _ts, layer in pool:
            if _victim(tag):
                b = by_tag.setdefault(tag, [0.0, 0])
                b[0] += amt
                b[1] = max(b[1], layer)
        for tag, (amt, layer) in by_tag.items():
            if amt > EPS:
                holdings.append({"party": party, "tag": tag, "amount": round(amt, 2), "as_of": st["end"],
                                 "has_statement": True, "layer": layer, "reconciles": reconciles})
    for party, tags in arrivals.items():
        for tag, (amt, layer, ts) in tags.items():
            holdings.append({"party": party, "tag": tag, "amount": round(amt, 2), "as_of": None,
                             "has_statement": False, "layer": layer, "reconciles": None, "arrived": ts})

    uncertain_parties = {i["party"] for i in issues}
    for h in holdings:
        h["uncertain"] = h["party"] in uncertain_parties
    for x in exits:
        x["uncertain"] = x["party"] in uncertain_parties

    by_case: dict[str, dict] = {}
    for s in seeds:
        c = by_case.setdefault(s["case_id"], {"loss": 0.0, "held": 0.0, "exited": 0.0, "missing_statement": 0.0})
        c["loss"] += s["amount"]
    for h in holdings:
        c = by_case.setdefault(h["tag"].split(":")[1], {"loss": 0.0, "held": 0.0, "exited": 0.0, "missing_statement": 0.0})
        c["held" if h["has_statement"] else "missing_statement"] += h["amount"]
    for x in exits:
        by_case[x["tag"].split(":")[1]]["exited"] += x["amount"]
    for c in by_case.values():
        for k in list(c):
            c[k] = round(c[k], 2)

    return {
        "method": method,
        "method_text": METHOD_TEXT[method],
        "seeds": seeds,
        "flows": flows,
        "holdings": sorted(holdings, key=lambda h: (-h["amount"], h["party"])),
        "exits": exits,
        "issues": issues,
        "reconciles": not issues,
        "by_case": by_case,
        "first_traced_in": first_traced_in,
        "missing_statements": sorted({h["party"] for h in holdings if not h["has_statement"]}),
        "total_loss": round(sum(s["amount"] for s in seeds), 2),
    }


def run_all(model: Model, skip_events: set[str] | None = None) -> dict:
    trails = {m: run(model, m, skip_events) for m in METHODS}
    spread: dict[str, dict] = {}
    for m, t in trails.items():
        for h in t["holdings"]:
            s = spread.setdefault(h["party"], {x: 0.0 for x in METHODS})
            s[m] = round(s[m] + h["amount"], 2)
    for party, s in spread.items():
        s["min"], s["max"] = min(s[x] for x in METHODS), max(s[x] for x in METHODS)
    return {"methods": trails, "spread": spread}
