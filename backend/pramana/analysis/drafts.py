"""Amount & Draft Assistant (F12).

One draft set = one lead, one scenario, one attribution method. Per account
it states the estimate under that method, the spread across methods, the
assumptions, the account's position in the trail and the observations that
mention it, and a draft request with the FIR reference and the lead's
Evidence Receipt attached.

It never sends anything, never decides whether a hold is lawful, never
clears an account holder. Every figure is an estimate and needs officer
approval before it is used.
"""
from __future__ import annotations

import hashlib
import json

from .trail import METHOD_TEXT, METHODS

DISCLAIMER = ("Decision support only. The legal basis and final action rest with the officer and the competent "
              "authority.")
MIN_AMOUNT = 1.0


def involved_parties(obs: dict) -> set[str]:
    out = {obs["subject"].get("value")} if obs["subject"]["kind"] == "party" else set()
    for k in ("sender_accounts", "path", "account_list", "shared_with"):
        out |= set(obs["metrics"].get(k, []))
    return {p for p in out if p}


def _downstream(result: dict, start: set[str], hours: float = 24) -> set[str]:
    """Accounts the lead's money moved on to quickly (within `hours` of the
    victim's payment). Later ordinary spending (rent, family transfers) is
    left out: a draft to a landlord for rent paid days later would be wrong."""
    from datetime import datetime, timedelta
    reach = set(start)
    seed_ts = {}
    for m in METHODS:
        for s in result["trail"]["methods"][m]["seeds"]:
            seed_ts[f"V:{s['case_id']}:{s['victim']}"] = datetime.fromisoformat(s["ts"])
    flows = [f for m in METHODS for f in result["trail"]["methods"][m]["flows"]]
    limit = timedelta(hours=hours)
    changed = True
    while changed:
        changed = False
        for f in flows:
            t0 = seed_ts.get(f["tag"])
            fast = t0 is not None and datetime.fromisoformat(f["ts"]) - t0 <= limit
            if f["from"] in reach and f["to"] not in reach and not f["exit"] and fast:
                reach.add(f["to"])
                changed = True
    return reach


def build_draft_set(obs: dict, result: dict, inp: dict, method: str, labels: dict[str, str]) -> dict:
    if method not in METHODS:
        raise ValueError(method)
    trail = result["trail"]["methods"][method]
    parties = _downstream(result, involved_parties(obs))
    cases = {c["id"]: c for c in inp["cases"]}
    case_ids = sorted({h["tag"].split(":")[1] for h in trail["holdings"] if h["party"] in parties}
                      | set(obs["cases"]))
    firs = ", ".join(f"FIR {cases[c]['fir_no']} ({c})" for c in case_ids if c in cases)

    holdings: dict[str, dict] = {}
    for h in trail["holdings"]:
        if h["party"] not in parties:
            continue
        x = holdings.setdefault(h["party"], {"amount": 0.0, "as_of": h["as_of"], "has_statement": h["has_statement"],
                                             "layer": h["layer"], "uncertain": h["uncertain"], "cases": set()})
        x["amount"] += h["amount"]
        x["layer"] = min(x["layer"], h["layer"])
        x["uncertain"] = x["uncertain"] or h["uncertain"]
        x["cases"].add(h["tag"].split(":")[1])

    sources_by_party: dict[str, set[str]] = {}
    events = {}
    for t in inp["transactions"]:
        events.setdefault(f"ref:{t['reference']}" if t["reference"] else f"row:{t['id']}", set()).add(t["source"])
    for f in trail["flows"]:
        sources_by_party.setdefault(f["to"], set()).update(events.get(f["event"], set()))

    ordinary = [o for o in result["observations"] if o["rule_id"] == "ORDINARY-PAYMENT-v1"]
    related = [o for o in result["observations"] if o["rule_id"] != "SHARED-ID-v1"]
    drafts = []
    for party, h in sorted(holdings.items(), key=lambda kv: -kv[1]["amount"]):
        if h["amount"] < MIN_AMOUNT:
            continue
        spread = result["trail"]["spread"].get(party, {})
        assumptions = [METHOD_TEXT[method]]
        if h["has_statement"]:
            assumptions.append(f"Estimate as of {h['as_of'][:10]}, the end of the statement in evidence; it is not a "
                               f"current balance.")
            assumptions.append("Opening balances are taken from the statements provided; other credits are treated "
                               "as the account holder's own funds.")
        else:
            assumptions.append("No statement for this account is in evidence: the figure is what arrived in it; "
                               "whether it is still there is unknown.")
        if h["uncertain"]:
            assumptions.append("Records for this account do not reconcile; the figure is uncertain and should not be "
                               "relied on without a complete statement.")
        assumptions.append(f"Range across attribution methods: Rs {spread.get('min', 0):,.2f} to "
                           f"Rs {spread.get('max', 0):,.2f} (a range across models, not a confidence interval).")
        notes = []
        for o in related:
            if party in involved_parties(o) or o["subject"].get("value") == party:
                notes.append(f"{o['title']} ({o['rule_id']})")
        for o in ordinary:
            if o["subject"]["label"].startswith(party):
                notes.append(f"Payment flagged for verification, purpose unverified - not cleared: {o['summary']}")
        label = labels.get(party, party)
        text = (
            f"To: The Nodal Officer, [bank holding account {party}]\n"
            f"Ref: {firs}\n\n"
            f"Subject: Request for account details and consideration of a hold on an estimated amount - "
            f"account {party}\n\n"
            f"In connection with the above case(s), analysis of the bank records received indicates that an estimated "
            f"Rs {h['amount']:,.2f} traceable to the reported transactions "
            + (f"was held in account {label} as of {h['as_of'][:10]}" if h["has_statement"]
               else f"was credited to account {label}")
            + f" (method: {method.upper()}; see assumptions).\n\n"
            f"You are requested to (1) furnish KYC, the account-opening form and the complete statement for the account, "
            f"and (2) consider placing a hold on the above amount under the applicable procedure, pending further "
            f"verification.\n\n"
            f"Assumptions:\n" + "\n".join(f"- {a}" for a in assumptions)
            + "\n\nAttached: Evidence Receipt for the lead \"" + obs["title"] + "\" (" + obs["key"] + ").\n\n"
            + DISCLAIMER
        )
        payload = {"party": party, "method": method, "amount": round(h["amount"], 2), "as_of": h["as_of"],
                   "sources": sorted(sources_by_party.get(party, set())), "input_hash": result["input_hash"],
                   "operations": result.get("operations", [])}
        drafts.append({
            "account_id": party, "label": label, "amount": round(h["amount"], 2), "as_of": h["as_of"],
            "estimate_min": spread.get("min"), "estimate_max": spread.get("max"),
            "method": method, "assumptions": assumptions, "notes": notes, "layer": h["layer"],
            "has_statement": h["has_statement"], "uncertain": h["uncertain"], "cases": sorted(h["cases"]),
            "sources": payload["sources"],
            "inputs_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "draft_text": text,
        })

    attributable = round(sum(x["amount"] for x in trail["holdings"]
                             if x["tag"].split(":")[1] in case_ids), 2)
    total = round(sum(d["amount"] for d in drafts), 2)
    return {"method": method, "drafts": drafts, "total": total, "attributable_under_method": attributable,
            "within_attributable": total <= attributable + 0.01, "case_ids": case_ids,
            "exits": [x for x in trail["exits"] if x["party"] in parties]}
