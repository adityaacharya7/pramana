"""Analysis: input snapshot (+ operations) -> observations, money trail,
reconciliation. Pure: no database, no clock, no randomness, so a handover
bundle re-run elsewhere gives the same result.
"""
from __future__ import annotations

from .. import __version__
from .inputs import input_hash
from .model import build_model
from .rules import RULES, convergence, default_params, rule_versions, run_rules
from .trail import METHODS, run_all

ENGINE_VERSION = "1.0.0"


def analyse(inp: dict, operations: list[dict] | None = None, params: dict | None = None) -> dict:
    ops = list(operations or [])
    model = build_model(inp, ops)
    trails = run_all(model)
    observations = run_rules(model, inp, trails, params)
    result = {
        "engine_version": ENGINE_VERSION,
        "software_version": __version__,
        "rule_versions": rule_versions(),
        "params": {**default_params(), **(params or {})},
        "input_hash": input_hash(inp),
        "operations": ops,
        "observations": observations,
        "trail": trails,
        "reconciles": all(trails["methods"][m]["reconciles"] for m in METHODS),
        # Convergence evaluated with no threshold, so a scenario that drops a
        # convergence finding can say how far below the threshold it fell.
        "near_misses": {o["key"]: o["metrics"] for o in convergence(
            model, {**default_params()["CONVERGENCE-v1"], **(params or {}).get("CONVERGENCE-v1", {}), "min_accounts": 1})},
    }
    disputed = [o["event_id"] for o in ops if o.get("op") == "dispute_txn"]
    if disputed:
        # Disputed: shown both with and without. The main result keeps the
        # transaction (flagged); this is the counterfactual.
        without = [o for o in ops if o.get("op") != "dispute_txn"] + [
            {"op": "simulate_no_txn", "event_id": e} for e in disputed]
        m2 = build_model(inp, without)
        t2 = run_all(m2)
        result["without_disputed"] = {"observations": run_rules(m2, inp, t2, params), "trail": t2,
                                      "reconciles": all(t2["methods"][m]["reconciles"] for m in METHODS)}
    return result


def summary(result: dict) -> dict:
    """The comparable core of a result: what a bundle re-run must reproduce."""
    obs = {o["key"]: {"rule": o["rule_id"], "metrics": _round(o["metrics"])} for o in result["observations"]}
    trail = {}
    for m in METHODS:
        t = result["trail"]["methods"][m]
        trail[m] = {"total_loss": t["total_loss"], "reconciles": t["reconciles"],
                    "holdings": sorted([h["party"], h["tag"], round(h["amount"], 2)] for h in t["holdings"]),
                    "exits": sorted([x["party"], x["kind"], x["tag"], round(x["amount"], 2)] for x in t["exits"])}
    return {"observations": obs, "trail": trail, "reconciles": result["reconciles"]}


def _round(v):
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def diff(before: dict, after: dict) -> dict:
    """What a scenario changes: findings removed / added / changed, and
    money-trail figures per account and method."""
    b = {o["key"]: o for o in before["observations"]}
    a = {o["key"]: o for o in after["observations"]}
    changed = []
    for k in sorted(set(b) & set(a)):
        if _round(b[k]["metrics"]) != _round(a[k]["metrics"]) or b[k]["independent_sources"] != a[k]["independent_sources"]:
            changed.append({"key": k, "title": a[k]["title"], "subject": a[k]["subject"]["label"],
                            "before": {"metrics": b[k]["metrics"], "summary": b[k]["summary"],
                                       "independent_sources": b[k]["independent_sources"]},
                            "after": {"metrics": a[k]["metrics"], "summary": a[k]["summary"],
                                      "independent_sources": a[k]["independent_sources"]}})
    removed = []
    for k in sorted(set(b) - set(a)):
        item = {"key": k, "title": b[k]["title"], "subject": b[k]["subject"]["label"], "summary": b[k]["summary"],
                "rule": b[k]["rule_id"], "why": "No longer produced by the rule on the remaining records."}
        near = after.get("near_misses", {}).get(k)
        if b[k]["rule_id"] == "CONVERGENCE-v1":
            need = after["params"]["CONVERGENCE-v1"]["min_accounts"]
            have = (near or {}).get("senders", 0)
            item["why"] = (f"Threshold not met: {have} of the {need} required complaint-linked senders remain "
                           f"within the window.")
            item["after_metrics"] = near
        removed.append(item)
    added = [{"key": k, "title": a[k]["title"], "subject": a[k]["subject"]["label"], "summary": a[k]["summary"],
              "rule": a[k]["rule_id"]} for k in sorted(set(a) - set(b))]

    estimates = []
    sb, sa = before["trail"]["spread"], after["trail"]["spread"]
    uncertain_after = {i["party"] for m in METHODS for i in after["trail"]["methods"][m]["issues"]}
    for party in sorted(set(sb) | set(sa)):
        eb, ea = sb.get(party), sa.get(party)
        vals_b = {m: (eb or {}).get(m, 0.0) for m in METHODS}
        vals_a = {m: (ea or {}).get(m, 0.0) for m in METHODS}
        if vals_b != vals_a or party in uncertain_after:
            estimates.append({"party": party, "before": vals_b, "after": vals_a,
                              "uncertain_after": party in uncertain_after})
    return {"removed": removed, "added": added, "changed": changed, "estimates": estimates,
            "reconciles_before": before["reconciles"], "reconciles_after": after["reconciles"],
            "issues_after": [i for m in METHODS for i in after["trail"]["methods"][m]["issues"]
                             if m == "fifo"]}


def dependencies(result: dict, source: str) -> list[dict]:
    """Findings that rest on records of `source`, and whether it is their only
    independent source (spec F11: listed before any operation)."""
    out = []
    for o in result["observations"]:
        srcs = {s["source"] for s in o["support"]}
        if source in srcs:
            out.append({"key": o["key"], "title": o["title"], "subject": o["subject"]["label"],
                        "independent_sources": len(srcs), "single_source": len(srcs) == 1})
    return out


def sources_of(result: dict, key: str) -> list[dict]:
    """Source groups behind one finding, for choosing what to challenge."""
    o = next((x for x in result["observations"] if x["key"] == key), None)
    if o is None:
        return []
    groups: dict[str, dict] = {}
    for s in o["support"]:
        g = groups.setdefault(s["source"], {"source": s["source"], "records": [], "events": set()})
        g["records"].append({k: s.get(k) for k in ("kind", "label", "file_id", "case_id", "span", "row")})
        if s.get("event_id"):
            g["events"].add(s["event_id"])
    return [{**g, "events": sorted(g["events"])} for g in groups.values()]


def receipt(obs: dict, inp: dict, result: dict) -> dict:
    """The Evidence Receipt (F10) for one observation."""
    files = {f["id"]: f for f in inp["files"]}
    support = []
    for s in obs["support"]:
        f = files.get(s["file_id"], {})
        support.append({**s, "filename": f.get("filename"), "sha256": f.get("sha256"), "kind_of_file": f.get("kind")})
    sources = {s["source"] for s in obs["support"]}
    file_ids = {s["file_id"] for s in obs["support"]}

    involved = {obs["subject"].get("value")}
    for k in ("sender_accounts", "path", "account_list", "shared_with"):
        involved |= set(obs["metrics"].get(k, []))
    unknowns = list(obs["unknowns"])
    missing = [p for p in result["trail"]["methods"]["fifo"]["missing_statements"] if p in involved]
    for p in missing:
        unknowns.append(f"No statement for {p}: where money went after reaching it is unknown (not evidence that it "
                        f"stayed there).")

    conflicts = []
    for q in inp.get("quality_issues", []):
        if set(q["file_ids"]) & file_ids:
            conflicts.append(f"Intake quality issue on a supporting file: {q['check'].replace('_', ' ')} "
                             f"({q['status'].lower()}).")
    ambiguous = {s["event_id"] for s in obs["support"] if s.get("event_id")} & {
        t["id"] for t in inp["transactions"] if t["ts_ambiguous"]}
    if ambiguous:
        conflicts.append("A supporting transaction has an ambiguous date (day and month could be swapped).")
    for op in result.get("operations", []):
        if op.get("op") == "dispute_txn" and op["event_id"] in {s.get("event_id") for s in obs["support"]}:
            conflicts.append(f"Transaction {op['event_id']} is disputed; results are shown with and without it.")
    for m in METHODS:
        for i in result["trail"]["methods"][m]["issues"]:
            if i["party"] in involved:
                msg = f"Records for {i['party']} do not reconcile ({i['kind'].replace('_', ' ')})."
                if msg not in conflicts:
                    conflicts.append(msg)

    return {
        "key": obs["key"], "title": obs["title"], "rule": {"id": obs["rule_id"], "version": obs["version"],
                                                           "params": result["params"].get(obs["rule_id"], {})},
        "observation": obs["summary"], "subject": obs["subject"], "cases": obs["cases"], "metrics": obs["metrics"],
        "supporting_records": support,
        "independent_sources": len(sources),
        "unknowns": unknowns,
        "conflicts": conflicts,
        "what_could_make_this_wrong": {
            "contradictions": conflicts or ["None found in the records reviewed."],
            "ordinary_explanation": obs["ordinary_explanation"],
            "records_that_would_distinguish": obs["distinguishing_records"],
            "independent_sources": len(sources),
            "note": "Copies of one record count once: two statements of one transfer share a bank reference, and "
                    "byte-identical files share a source group.",
        },
        "next_verification_step": obs["next_step"],
        "input_hash": result["input_hash"],
        "rule_catalogue_title": RULES[obs["rule_id"]]["title"],
    }
