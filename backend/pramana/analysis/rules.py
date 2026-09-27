"""Detection rules library (F9): eight versioned rules with configurable
thresholds. Each outputs *observations* - never labels about people - with the
records that support them and the questions that remain open.

Wording follows the spec: "lead", "observation", "account holder",
"potential connection". No rule scores suspicion.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from . import mo
from .model import Event, Model, is_special
from .trail import METHODS

RULES: dict[str, dict] = {
    "SHARED-ID-v1": {"title": "Identifier shared across cases", "params": {"min_cases": 2}},
    "CONVERGENCE-v1": {"title": "Potential convergence point", "params": {"min_accounts": 3, "window_minutes": 60}},
    "LAYERING-v1": {"title": "Rapid pass-through chain",
                    "params": {"min_hops": 3, "chain_hours": 24, "forward_ratio": 0.8, "forward_within_hours": 2}},
    "CASHOUT-v1": {"title": "Probable exit point", "params": {"within_hours": 6}},
    "FACILITATOR-v1": {"title": "Common account-opening pattern", "params": {"min_accounts": 3}},
    "FRONT-ENTITY-v1": {"title": "Business account to verify", "params": {"max_age_days": 90, "min_credits": 2}},
    "MO-MATCH-v1": {"title": "Similar MO: proposed for comparison, not evidence of a shared operation",
                    "params": {"min_score": 0.45, "min_attribute_types": 2, "method": mo.METHOD}},
    "ORDINARY-PAYMENT-v1": {"title": "Possible ordinary merchant payment; purpose and recipient involvement unverified",
                            "params": {"max_share": 0.05, "within_hours": 24}},
}


def rule_versions() -> dict[str, str]:
    return {r: r.rsplit("-v", 1)[1] for r in RULES}


def default_params() -> dict[str, dict]:
    return {r: dict(v["params"]) for r, v in RULES.items()}


# --- helpers ------------------------------------------------------------------------

def party_label(model: Model, p: str) -> str:
    k = model.kyc.get(p)
    holders = [h["name"] for h in (k or {}).get("holders", [])]
    names = holders or model.names.get(p, [])
    return f"{p} ({', '.join(names[:2])})" if names else p


def event_support(e: Event, role: str = "support", note: str = "") -> list[dict]:
    return [{"kind": "bank record", "event_id": e.id, "file_id": r["file_id"], "case_id": r["case_id"],
             "span": r["span"], "row": r["row"], "source": r["source"], "role": role,
             "label": f"{e.ts[:16].replace('T', ' ')}  {e.src} -> {e.dst}  Rs {e.amount:,.2f}",
             "note": note} for r in e.rows]


def _obs(rule: str, subject: dict, summary: str, cases, support, metrics, *, unknowns=(), ordinary="",
         distinguishing=(), next_step="", key_suffix=None, extra=None) -> dict:
    return {
        "key": f"{rule}:{key_suffix or subject['value']}", "rule_id": rule, "version": rule.rsplit("-v", 1)[1],
        "title": RULES[rule]["title"], "subject": subject, "summary": summary, "cases": sorted(set(cases)),
        "support": support, "metrics": metrics, "unknowns": list(unknowns), "ordinary_explanation": ordinary,
        "distinguishing_records": list(distinguishing), "next_step": next_step, **(extra or {}),
    }


def _events_by_party(model: Model):
    out_ev, in_ev = defaultdict(list), defaultdict(list)
    for e in model.events:
        out_ev[e.src].append(e)
        in_ev[e.dst].append(e)
    return out_ev, in_ev


# --- the rules ----------------------------------------------------------------------

def shared_id(model: Model, inp: dict, p: dict) -> list[dict]:
    by_value: dict[tuple, list[dict]] = defaultdict(list)
    for m in model.mentions:
        by_value[(m["type"], m["value"])].append(m)
    complainant_phones = {ph["value"] for c in model.complaints for ph in c.get("complainant_phones", [])}
    out = []
    for (etype, value), ms in sorted(by_value.items()):
        cases = sorted({m["case_id"] for m in ms})
        if len(cases) < p["min_cases"]:
            continue
        names = sorted({n for m in ms for n in m.get("names_seen", [])})
        support, seen = [], set()
        for m in ms:
            k = (m["case_id"], m["file_id"])
            if k in seen:
                continue
            seen.add(k)
            support.append({"kind": "mention", "file_id": m["file_id"], "case_id": m["case_id"], "span": m["span"],
                            "source": m["source"], "role": "support", "label": f"{etype} {value} in {m['case_id']}",
                            "note": ""})
        if value in complainant_phones:
            ordinary = ("This is a complainant's own number. Appearing in another case's call records usually means "
                        "that complainant was called, not that the cases share a caller.")
        elif any(w in " ".join(names).lower() for w in ("power", "electric", "bill", "stores", "mart")):
            ordinary = ("The identifier belongs to a utility biller or merchant that many unrelated customers pay "
                        "(a known merchant category).")
        else:
            ordinary = ("Numbers are reused, shared within families, recycled by telecom operators or mistyped. A "
                        "shared identifier links records, not people.")
        nxt = {"phone": "Request subscriber details (CAF) and call records for the number; compare timing of use in "
                        "each case.",
               "bank_account": "Request KYC and the full statement from the bank for this account.",
               "upi": "Request the UPI ID's linked account and KYC from the payment provider.",
               "imei": "Request the handset's SIM history from telecom operators.",
               "crypto_wallet": "Request exchange KYC for the wallet, if custodial; trace its transactions on-chain."
               }.get(etype, "Verify who controlled the identifier in each case.")
        out.append(_obs("SHARED-ID-v1", {"kind": "identifier", "type": etype, "value": value,
                                         "label": f"{etype.replace('_', ' ')} {value}" + (f" ({', '.join(names[:2])})" if names else "")},
                        f"The {etype.replace('_', ' ')} {value} appears in {len(cases)} cases: {', '.join(cases)}.",
                        cases, support, {"cases": len(cases)},
                        unknowns=["Who used or controlled the identifier at the time of each case."],
                        ordinary=ordinary,
                        distinguishing=["Subscriber / KYC records for the identifier",
                                        "When and how it was used in each case"],
                        next_step=nxt, key_suffix=f"{etype}:{value}"))
    return out


def convergence(model: Model, p: dict) -> list[dict]:
    _, in_ev = _events_by_party(model)
    win = timedelta(minutes=p["window_minutes"])
    out = []
    for party, evs in in_ev.items():
        if is_special(party) or party in model.victim_parties:
            continue
        evs = sorted((e for e in evs if e.src in model.complaint_linked and e.src != party), key=lambda e: e.dt)
        best: list[Event] = []
        for i, e0 in enumerate(evs):
            window = [e for e in evs[i:] if e.dt - e0.dt <= win]
            if len({e.src for e in window}) > len({e.src for e in best}):
                best = window
        senders = sorted({e.src for e in best})
        if len(senders) < p["min_accounts"]:
            continue
        support = [s for e in best for s in event_support(e)]
        cases = [r["case_id"] for e in best for r in e.rows]
        mins = int((best[-1].dt - best[0].dt).total_seconds() // 60)
        total = round(sum(e.amount for e in best), 2)
        unknowns = ["Beneficial owner of the receiving account has not been established."]
        k = model.kyc.get(party)
        if k and (k.get("holder_type", "").lower() != "individual"):
            unknowns.append("Whether the account's other credits are ordinary business receipts.")
        missing = [s for s in senders if s not in model.statements]
        if missing:
            unknowns.append(f"No statement for {len(missing)} sending account(s); their other movements are unknown.")
        out.append(_obs("CONVERGENCE-v1", {"kind": "party", "value": party, "label": party_label(model, party)},
                        f"{len(senders)} complaint-linked accounts sent Rs {total:,.2f} to {party_label(model, party)} "
                        f"within {mins} minutes.",
                        cases, support,
                        {"senders": len(senders), "window_minutes": mins, "amount": total,
                         "sender_accounts": senders, "events": [e.id for e in best]},
                        unknowns=unknowns,
                        ordinary="A legitimate collection account (a merchant, housing society or payment aggregator) "
                                 "receiving several customers' payments close together.",
                        distinguishing=["KYC and account-opening documents of the receiving account",
                                        "Its full statement and declared business",
                                        "Whether the senders had any dealings with it before"],
                        next_step=f"Request KYC, beneficial-ownership details and the full statement of {party}; "
                                  "verify each sender's relationship to it."))
    return out


def layering(model: Model, p: dict) -> list[dict]:
    out_ev, _ = _events_by_party(model)
    within = timedelta(hours=p["forward_within_hours"])
    horizon = timedelta(hours=p["chain_hours"])

    def extend(party: str, amount: float, t: datetime, start: datetime, chain: list[Event], seen: set):
        onward = [e for e in out_ev.get(party, []) if t < e.dt <= t + within and not is_special(e.dst)
                  and e.dst not in seen]
        best = chain
        if onward and sum(e.amount for e in onward) >= p["forward_ratio"] * amount:
            for e in onward:
                if e.dt - start > horizon:
                    continue
                c = extend(e.dst, e.amount, e.dt, start, chain + [e], seen | {e.dst})
                if len(c) > len(best):
                    best = c
        return best

    out = []
    for e0 in model.events:
        case = model.seed_case(e0)
        if not case:
            continue
        chain = extend(e0.dst, e0.amount, e0.dt, e0.dt, [e0], {e0.src, e0.dst})
        if len(chain) < p["min_hops"]:
            continue
        path = [chain[0].src] + [e.dst for e in chain]
        mins = int((chain[-1].dt - chain[0].dt).total_seconds() // 60)
        support = [s for e in chain for s in event_support(e)]
        out.append(_obs("LAYERING-v1", {"kind": "chain", "value": e0.id, "label": " -> ".join(path)},
                        f"Money from the complaint in {case} passed through {len(chain)} accounts in {mins} minutes, "
                        f"each forwarding at least {int(p['forward_ratio'] * 100)}% within {p['forward_within_hours']} h: "
                        + " -> ".join(party_label(model, x) for x in path) + ".",
                        [case] + [r["case_id"] for e in chain for r in e.rows], support,
                        {"hops": len(chain), "minutes": mins, "path": path, "events": [e.id for e in chain],
                         "amounts": [e.amount for e in chain]},
                        unknowns=["Purpose each account holder gives for the onward transfers.",
                                  "Whether the account holders operated these accounts themselves."],
                        ordinary="Money passed on quickly for ordinary reasons, such as a trader settling supplier "
                                 "invoices on receipt.",
                        distinguishing=["Each holder's statement of the transfer's purpose",
                                        "Invoices or agreements behind each transfer",
                                        "Device and IP logs of the transfers"],
                        next_step="Request KYC, statements and transfer device/IP logs for every account in the chain.",
                        key_suffix=e0.id))
    return out


def cashout(model: Model, trails: dict, p: dict) -> list[dict]:
    within = timedelta(hours=p["within_hours"])
    traced_in: dict[str, list[datetime]] = defaultdict(list)
    for m in METHODS:
        for f in trails["methods"][m]["flows"]:
            if not f["exit"]:
                traced_in[f["to"]].append(datetime.fromisoformat(f["ts"]))
    by_party: dict[str, list[Event]] = defaultdict(list)
    for e in model.events:
        if e.src not in traced_in:
            continue
        kind = ("crypto" if e.reference and e.reference in model.trade_links
                else "cash" if is_special(e.dst) and e.dst != "BANK_CHARGES" else None)
        if not kind:
            continue
        if any(t <= e.dt <= t + within for t in traced_in[e.src]):
            by_party[e.src].append(e)
    out = []
    for party, evs in by_party.items():
        support, wallets = [], []
        for e in evs:
            support += event_support(e)
            for tr in model.trade_links.get(e.reference, []):
                support.append({"kind": "trade record", "file_id": tr["file_id"], "case_id": tr["case_id"],
                                "span": tr["reference_span"], "source": tr["source"], "role": "support",
                                "label": f"{tr['filename']}: payment reference {e.reference}", "note": ""})
                for w in tr["wallets"]:
                    wallets.append(w["value"])
                    support.append({"kind": "trade record", "file_id": tr["file_id"], "case_id": tr["case_id"],
                                    "span": w["span"], "source": tr["source"], "role": "support",
                                    "label": f"{tr['filename']}: destination wallet {w['value']}", "note": ""})
        crypto = any(e.reference in model.trade_links for e in evs)
        total = round(sum(e.amount for e in evs), 2)
        what = ("converted to crypto per a trade record" if crypto else "withdrawn in cash")
        out.append(_obs("CASHOUT-v1", {"kind": "party", "value": party, "label": party_label(model, party)},
                        f"Rs {total:,.2f} left the banking trail from {party_label(model, party)} within "
                        f"{p['within_hours']} h of it receiving traced funds ({what})"
                        + (f"; destination wallet {', '.join(sorted(set(wallets)))}." if wallets else "."),
                        [r["case_id"] for e in evs for r in e.rows] + [s["case_id"] for s in support], support,
                        {"exits": len(evs), "amount": total, "wallets": sorted(set(wallets)),
                         "events": [e.id for e in evs]},
                        unknowns=(["Who controls the destination wallet."] if crypto else
                                  ["Who made the withdrawals (card holder, or someone else)."]),
                        ordinary=("A lawful peer-to-peer crypto purchase with the account holder's own money."
                                  if crypto else "The account holder withdrawing their own money."),
                        distinguishing=(["Exchange KYC for the wallet", "On-chain history of the wallet",
                                         "The seller's records of the buyer"] if crypto else
                                        ["ATM CCTV and withdrawal location", "Card and PIN usage records"]),
                        next_step=("Request exchange/KYC details for the wallet and trace the TXID on-chain."
                                   if crypto else "Request ATM CCTV and withdrawal records for these transactions."),
                        extra={"exit_kind": "crypto" if crypto else "cash"}))
    return out


def facilitator(model: Model, p: dict) -> list[dict]:
    groups: dict[tuple, list[str]] = defaultdict(list)
    for party, k in model.kyc.items():
        if party not in model.complaint_linked or party in model.victim_parties:
            continue
        if k.get("branch") and k.get("official"):
            groups[("branch+official", f"{k['branch']} / {k['official']}")].append(party)
        if k.get("kyc_doc_sha256"):
            groups[("KYC document", k["kyc_doc_sha256"])].append(party)
        if k.get("device_id_at_opening"):
            groups[("opening device", k["device_id_at_opening"])].append(party)
    out = []
    for (basis, value), parties in sorted(groups.items()):
        if len(parties) < p["min_accounts"]:
            continue
        support = []
        for party in sorted(parties):
            for r in model.kyc[party]["records"]:
                support.append({"kind": "account-opening record", "file_id": r["file_id"], "case_id": r["case_id"],
                                "span": r["span"], "source": r["source"], "role": "support",
                                "label": f"{party}: opened at {model.kyc[party].get('branch')} by "
                                         f"{model.kyc[party].get('official')} on {model.kyc[party].get('opening_date', '?')}",
                                "note": ""})
        official = next((model.kyc[x].get("official_name") for x in parties if model.kyc[x].get("official_name")), None)
        out.append(_obs("FACILITATOR-v1", {"kind": basis, "value": value,
                                           "label": f"{value}" + (f" ({official})" if official else "")},
                        f"{len(parties)} complaint-linked accounts share the same {basis}: {value}.",
                        [s["case_id"] for s in support], support,
                        {"accounts": len(parties), "account_list": sorted(parties), "basis": basis},
                        unknowns=["How many accounts the same branch and official opened in the period overall.",
                                  "Whether the account holders were present and verified in person."],
                        ordinary="A branch where one official opens most new accounts in the normal course of work.",
                        distinguishing=["The branch's total account openings by that official in the period",
                                        "Account-opening forms, photographs and video-KYC records"],
                        next_step="Request account-opening forms, KYC documents and in-person / video-KYC records for "
                                  "these accounts from the branch.",
                        key_suffix=f"{basis}:{value}"))
    return out


def front_entity(model: Model, p: dict, flagged: set[str]) -> list[dict]:
    _, in_ev = _events_by_party(model)
    out = []
    for party, k in model.kyc.items():
        business = (k.get("holder_type", "").lower() not in ("", "individual")) or k.get("account_type") == "Current"
        if not business or not k.get("opening_date"):
            continue
        credits = sorted((e for e in in_ev.get(party, []) if e.src in model.complaint_linked), key=lambda e: e.dt)
        if len(credits) < p["min_credits"]:
            continue
        opened = datetime.fromisoformat(k["opening_date"] + "T00:00:00+05:30")
        if (credits[0].dt - opened).days > p["max_age_days"]:
            continue
        mine_phones = set(k.get("phones", []))
        mine_addr = {h.get("address") for h in k.get("holders", []) if h.get("address")}
        shared_with = []
        for other in flagged - {party}:
            ok = model.kyc.get(other)
            if not ok:
                continue
            if mine_phones & set(ok.get("phones", [])) or mine_addr & {h.get("address") for h in ok.get("holders", [])}:
                shared_with.append(other)
        if not shared_with:
            continue  # the rule needs a shared address or phone with another flagged entity
        support = [s for e in credits for s in event_support(e)]
        for r in k["records"]:
            support.append({"kind": "account-opening record", "file_id": r["file_id"], "case_id": r["case_id"],
                            "span": r["span"], "source": r["source"], "role": "support",
                            "label": f"{party}: {k.get('holder_type')} {k.get('account_type')} account opened "
                                     f"{k['opening_date']}", "note": ""})
        out.append(_obs("FRONT-ENTITY-v1", {"kind": "party", "value": party, "label": party_label(model, party)},
                        f"Business account {party_label(model, party)} opened {k['opening_date']} received "
                        f"{len(credits)} complaint-linked credits and shares a phone or address with "
                        f"{', '.join(shared_with)}.",
                        [s["case_id"] for s in support], support,
                        {"credits": len(credits), "shared_with": sorted(shared_with)},
                        unknowns=["Whether the business trades as declared."],
                        ordinary="A new small business using a partner's or relative's phone or address.",
                        distinguishing=["Business registration, GST filings and trading records"],
                        next_step="Verify the business's registration and trading activity; request partnership deed."))
    return out


def mo_match(model: Model, p: dict, shared_pairs: set[frozenset]) -> list[dict]:
    docs: dict[str, str] = {}
    spans: dict[str, tuple[str, str]] = {}
    for c in model.complaints:
        docs[c["case_id"]] = docs.get(c["case_id"], "") + ("\n" if c["case_id"] in docs else "") + c["text"]
        spans.setdefault(c["case_id"], (c["file_id"], c["source"]))
    if len(docs) < 2:
        return []
    scores = mo.mo_scores(docs)
    out = []
    for (a, b), s in sorted(scores.items()):
        if s["score"] < p["min_score"] or len(s["matching_attribute_types"]) < p["min_attribute_types"]:
            continue
        support = []
        for cid in (a, b):
            file_id, source = spans[cid]
            text = next(c["text"] for c in model.complaints if c["file_id"] == file_id)
            attrs = mo.attributes(text)
            for attr, items in attrs.items():
                for it in items:
                    if f"{attr}:{it['value']}" in s["shared"]:
                        support.append({"kind": "complaint passage", "file_id": file_id, "case_id": cid,
                                        "span": it["span"], "source": source, "role": "support",
                                        "label": f"{cid}: {attr.replace('_', ' ')} = {it['value']}",
                                        "note": text[it["span"][0]:it["span"][1]]})
        shared = frozenset((a, b)) in shared_pairs
        out.append(_obs("MO-MATCH-v1", {"kind": "case pair", "value": f"{a}|{b}", "label": f"{a} and {b}"},
                        f"{a} and {b} describe a similar method (score {s['score']:.2f}; "
                        f"{len(s['matching_attribute_types'])} matching attribute types). "
                        + ("They also share an identifier." if shared else
                           "They share no identifier: a similar method alone is not evidence of a shared operation."),
                        [a, b], support,
                        {"score": s["score"], "attribute_cosine": s["attribute_cosine"],
                         "text_cosine": s["text_cosine"], "matching_attribute_types": s["matching_attribute_types"],
                         "shared_attributes": s["shared"], "shared_identifier": shared},
                        unknowns=["Whether the same people are behind both cases."],
                        ordinary="Widely circulated scripts: unrelated groups copy the same method.",
                        distinguishing=["A common account, phone, device or wallet across the cases"],
                        next_step="Compare the two complaints side by side and look for a shared account, phone or "
                                  "device before treating them as linked.",
                        key_suffix=f"{a}|{b}"))
    return out


def ordinary_payment(model: Model, trails: dict, p: dict) -> list[dict]:
    within = timedelta(hours=p["within_hours"])
    traced_amount: dict[str, float] = defaultdict(float)
    first_in: dict[str, datetime] = {}
    for f in trails["methods"]["prorata"]["flows"]:
        if not f["exit"]:
            traced_amount[f["to"]] += f["amount"]
            t = datetime.fromisoformat(f["ts"])
            first_in[f["to"]] = min(first_in.get(f["to"], t), t)
    out, seen = [], set()
    for e in model.events:
        if e.src not in first_in or e.channel != "UPI-P2M" or e.dst in model.statements or e.id in seen:
            continue
        if not (first_in[e.src] <= e.dt <= first_in[e.src] + within):
            continue
        received = max((sum(x["amount"] for x in trails["methods"][m]["flows"]
                            if x["to"] == e.src and not x["exit"]) for m in METHODS), default=0.0)
        if received <= 0 or e.amount > p["max_share"] * received:
            continue
        seen.add(e.id)
        history = sum(1 for x in model.events if x.src == e.src and x.dst == e.dst and x.dt < first_in[e.src])
        name = ", ".join(e.names) or e.dst
        out.append(_obs("ORDINARY-PAYMENT-v1", {"kind": "event", "value": e.id, "label": f"{e.src} -> {name}"},
                        f"Rs {e.amount:,.2f} paid from {party_label(model, e.src)} to {name} while it held traced "
                        f"funds ({e.amount / received:.1%} of the Rs {received:,.2f} traced into it). "
                        + (f"The account paid this merchant {history} time(s) before. " if history else "")
                        + "Flagged for verification, not cleared.",
                        list(e.cases), event_support(e),
                        {"amount": e.amount, "share": round(e.amount / received, 4), "prior_payments": history},
                        unknowns=["Purpose of the payment and whether the merchant knew of the funds' origin."],
                        ordinary="An everyday purchase by the account holder.",
                        distinguishing=["The merchant's records of the sale", "The account holder's statement"],
                        next_step="Verify the purchase with the merchant; do not treat the merchant as involved "
                                  "without further evidence.",
                        key_suffix=e.id))
    return out


def run_rules(model: Model, inp: dict, trails: dict, params: dict | None = None) -> list[dict]:
    p = default_params()
    for k, v in (params or {}).items():
        p.setdefault(k, {}).update(v)
    obs = []
    ids = shared_id(model, inp, p["SHARED-ID-v1"])
    obs += ids
    obs += convergence(model, p["CONVERGENCE-v1"])
    obs += layering(model, p["LAYERING-v1"])
    obs += cashout(model, trails, p["CASHOUT-v1"])
    obs += facilitator(model, p["FACILITATOR-v1"])
    flagged = {o["subject"]["value"] for o in obs if o["subject"]["kind"] == "party"}
    for o in obs:
        flagged |= set(o["metrics"].get("account_list", [])) | set(o["metrics"].get("path", []))
    obs += front_entity(model, p["FRONT-ENTITY-v1"], flagged)
    shared_pairs = set()
    for o in ids:
        # Billers and merchants that many unrelated customers pay are not a
        # link between cases.
        if "merchant category" in o["ordinary_explanation"] or len(o["cases"]) > 5:
            continue
        cs = o["cases"]
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                shared_pairs.add(frozenset((a, b)))
    obs += mo_match(model, p["MO-MATCH-v1"], shared_pairs)
    obs += ordinary_payment(model, trails, p["ORDINARY-PAYMENT-v1"])
    for o in obs:
        o["independent_sources"] = len({s["source"] for s in o["support"]})
    return sorted(obs, key=lambda o: (list(RULES).index(o["rule_id"]), o["key"]))
