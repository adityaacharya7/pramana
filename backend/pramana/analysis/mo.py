"""Modus-operandi profiles and similarity (F7).

Two parts, both required by MO-MATCH-v1:

* **Attributes** read from the complaint by fixed rules, each with the passage
  it came from: impersonated agency, pretext, payment instruction, contact
  channel, duration. English, Hinglish and Hindi cues.
* **Similarity score** = 0.7 x cosine of the two attribute profiles + 0.3 x
  cosine of TF-IDF vectors (word 1-2 grams) of the narratives. Text alone
  did not separate the cases on the demo data: hand-written narratives of
  one script scored lower than unrelated complaints built from one template,
  so the structured profile carries most of the weight. The spec names a multilingual
  sentence-embedding model; that model needs PyTorch, which the offline and
  serverless builds do not carry, so this deterministic method is used and
  its threshold is set for it (a TF-IDF cosine is not on the same scale as an
  embedding cosine). The method is recorded with every result.

A similar MO is a reason to compare two cases, never evidence of a shared
operation.
"""
from __future__ import annotations

import math
import re
from collections import Counter

METHOD = "mo-attributes-0.7+tfidf-1-2gram-0.3-v1"
ATTR_WEIGHT, TEXT_WEIGHT = 0.7, 0.3

ATTRIBUTES: dict[str, list[tuple[str, str]]] = {
    "impersonated_agency": [
        ("CBI", r"\bcbi\b"), ("Customs", r"\bcustoms\b"), ("Narcotics Control Bureau", r"narcotics control bureau|\bncb\b"),
        ("Enforcement Directorate", r"enforcement directorate"), ("Telecom Department / TRAI", r"telecom department|\btrai\b"),
        ("Police", r"mumbai police|cyber crime branch|police se hai"), ("RBI", r"\brbi\b|reserve bank"),
        ("Electricity officer", r"electricity officer|bijli"), ("Army officer", r"army officer|आर्मी ऑफिसर"),
        ("Customer care", r"customer care"), ("Courier company", r"courier"), ("SEBI-registered advisor", r"\bsebi\b"),
        ("Bank", r"account will be\s+blocked|खाता आज बंद"),
    ],
    "pretext": [
        ("SIM / Aadhaar misuse in money laundering", r"sim card|sim used|money laundering"),
        ("Parcel with drugs or passports", r"parcel.{0,160}(drugs|mdma|passport)|(drugs|mdma|passports).{0,160}parcel"),
        ("KYC / account block", r"\bkyc\b"),
        ("Electricity disconnection", r"(electricity|power|bijli)[^.]{0,60}(disconnect|kaat)"),
        ("Part-time job tasks", r"part-time job|task"),
        ("Investment / trading returns", r"stock tips|trading|ipo|crypto trading"),
        ("Loan app harassment", r"loan"), ("Marketplace purchase", r"marketplace|बेचने का विज्ञापन"),
        ("Customs duty on a gift parcel", r"customs duty"), ("Refund of a cancelled booking", r"refund for|refund of|cancelled [a-z]+ booking"),
    ],
    "payment_instruction": [
        ("Transfer to an 'RBI' verification / custody account", r"rbi[^.]{0,40}(verification|custody|supervis)|(verification|custody|supervision) account|secure custody|supervisory account"),
        ("Refund promised after verification", r"(returned|refunded|refund ho)[^.]{0,60}(verification|enquiry|24 hours|24 ghante)"),
        ("Prepaid task deposits", r"prepaid"), ("Scan QR code to 'receive' money", r"qr code"),
        ("Fee to release money", r"clearance|processing fee|service charge|\btax\b"),
        ("Remote-access app", r"install[^.]{0,40}app|app download"),
    ],
    "contact_channel": [
        ("Video call", r"video call|skype"), ("WhatsApp", r"whatsapp"), ("Telegram", r"telegram"),
        ("SMS link", r"\bsms\b|link"), ("Phone call", r"\bcall(ed)? (from|on)|received a call|se call aaya|फोन"),
        ("Social media", r"instagram"),
    ],
    "duration": [
        ("Multi-day 'digital arrest'", r"digital arrest"), ("Held on call for hours or days",
                                                               r"(\d+|two|three) (hours|days)|do din|for most of the day"),
    ],
}
_COMPILED = {k: [(label, re.compile(p, re.IGNORECASE)) for label, p in v] for k, v in ATTRIBUTES.items()}

STOP = set("""a an the and or of to in on at for from by with as is was were be been it its this that these those i
me my we our you your he she him her his they them their not no but if then so than too very can will would
shall should may might must do did does done have has had about into over under after before during between
also am are sir madam rs mr mrs smt dear please kindly request complaint hai hain mein ko ki ke se par aur ne
bhi tha thi kiya diya gaya maine mujhe unhone""".split())
TOKEN = re.compile(r"[a-z][a-z']+")


def attributes(text: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for attr, pats in _COMPILED.items():
        for label, pat in pats:
            m = pat.search(text)
            if m:
                out.setdefault(attr, []).append({"value": label, "span": [m.start(), m.end()]})
    return out


def _grams(text: str) -> Counter:
    words = [w for w in TOKEN.findall(text.lower()) if w not in STOP and len(w) > 2]
    grams = Counter(words)
    grams.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return grams


def similarity_matrix(docs: dict[str, str]) -> dict[tuple[str, str], float]:
    """Pairwise cosine similarity of TF-IDF vectors; deterministic for a
    given set of documents."""
    grams = {k: _grams(v) for k, v in docs.items()}
    n = len(grams)
    df = Counter(g for c in grams.values() for g in c)
    idf = {g: math.log((1 + n) / (1 + d)) + 1.0 for g, d in df.items()}
    vecs = {}
    for k, c in grams.items():
        v = {g: (1 + math.log(tf)) * idf[g] for g, tf in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[k] = {g: x / norm for g, x in v.items()}
    keys = sorted(vecs)
    out = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            va, vb = vecs[a], vecs[b]
            small, big = (va, vb) if len(va) < len(vb) else (vb, va)
            out[(a, b)] = round(sum(x * big.get(g, 0.0) for g, x in small.items()), 4)
    return out


def profile(attrs: dict[str, list[dict]]) -> set[str]:
    return {f"{k}:{x['value']}" for k, v in attrs.items() for x in v}


def mo_scores(docs: dict[str, str]) -> dict[tuple[str, str], dict]:
    """Per case pair: combined score, its parts, and the attributes both share."""
    text = similarity_matrix(docs)
    attrs = {k: attributes(v) for k, v in docs.items()}
    out = {}
    for (a, b), t in text.items():
        pa, pb = profile(attrs[a]), profile(attrs[b])
        cos = len(pa & pb) / math.sqrt(len(pa) * len(pb)) if pa and pb else 0.0
        shared_types = sorted({x.split(":", 1)[0] for x in pa & pb})
        out[(a, b)] = {"score": round(ATTR_WEIGHT * cos + TEXT_WEIGHT * t, 4), "attribute_cosine": round(cos, 4),
                       "text_cosine": t, "shared": sorted(pa & pb), "matching_attribute_types": shared_types}
    return out
