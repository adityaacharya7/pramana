"""Deterministic identifier rules: pattern + validator + normaliser.

Identifiers are what cross-case links rest on, so they are extracted by
rules that behave the same way every time, not by a model.
"""
from __future__ import annotations

import re

# Entity types (spec, "Data model").
PERSON, ORG, PHONE, ACCOUNT, UPI, IMEI, WALLET = "person", "organisation", "phone", "bank_account", "upi", "imei", "crypto_wallet"
BRANCH, OFFICIAL, LOCATION, DOCUMENT = "bank_branch", "bank_official", "location", "document"
# Extracted and reviewed, but kept as an attribute of the person in the same
# record rather than becoming a graph node.
ID_DOCUMENT = "id_document"

IDENTIFIER_TYPES = {PHONE, ACCOUNT, UPI, IMEI, WALLET, BRANCH, OFFICIAL}
NAMED_TYPES = {PERSON, ORG}

PHONE_RE = re.compile(r"(?<![\w+])(?:\+?91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
UPI_RE = re.compile(r"(?<![\w.@-])([a-zA-Z0-9][a-zA-Z0-9._-]{1,63}@[a-zA-Z][a-zA-Z0-9]{1,63})(?![\w@]|\.[a-zA-Z])")
WALLET_RE = re.compile(r"\b(T[1-9A-HJ-NP-Za-km-z]{33}|0x[0-9a-fA-F]{40}|bc1[02-9ac-hj-np-z]{25,59})\b")
AADHAAR_MASKED_RE = re.compile(r"\b(X{4}-X{4}-\d{4})\b")
IMEI_RE = re.compile(r"(?<!\d)(\d{15})(?!\d)")
# Account numbers are only taken with an account keyword in front of them:
# a bare 12-digit number is as likely to be a UTR, an acknowledgement
# number or a phone with a country code.
ACCOUNT_RE = re.compile(
    r"(?:account(?:\s+(?:number|no\.?))?|a/c(?:\s+no\.?)?|acct|khata|खाता(?:\s+संख्या)?|मेरा खाता)"
    r"\s*(?:is\s+|:\s*|no\.?\s*:?\s*)?(\d(?:[ ]?\d){8,17})(?!\d)",
    re.IGNORECASE,
)
OFFICIAL_RE = re.compile(r"^[A-Z]{1,3}-\d{1,5}$")


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def normalise_phone(s: str) -> str | None:
    d = digits(s)
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return d if len(d) == 10 and d[0] in "6789" else None


def luhn_ok(num: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def normalise_account(s: str) -> str | None:
    d = digits(s)
    return d if 9 <= len(d) <= 18 else None


def normalise_upi(s: str) -> str | None:
    s = s.strip().lower()
    return s if UPI_RE.fullmatch(s) else None


HONORIFICS = re.compile(
    r"^(?:mr|mrs|ms|smt|shri|sri|dr|prof|insp|inspector|sub-inspector|si|asi|psi|dcp|acp|sp|dysp|officer|"
    r"professor|captain|major|col|colonel)\.?\s+",
    re.IGNORECASE,
)


def normalise_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().strip(",.;:()\"'"))
    while True:
        t = HONORIFICS.sub("", s)
        if t == s:
            break
        s = t
    # Short all-caps words are acronyms or initials (CBI, RBI, "C"): keep them.
    return " ".join(w if (w.isupper() and len(w) <= 4) or (len(w) == 2 and w.endswith(".")) else w.title()
                    for w in s.split())


def canonical(entity_type: str, raw: str) -> str | None:
    if entity_type == PHONE:
        return normalise_phone(raw)
    if entity_type == ACCOUNT:
        return normalise_account(raw)
    if entity_type == UPI:
        return normalise_upi(raw)
    if entity_type == IMEI:
        d = digits(raw)
        return d if len(d) == 15 and luhn_ok(d) else None
    if entity_type == WALLET:
        return raw.strip()
    if entity_type == BRANCH:
        m = IFSC_RE.fullmatch(raw.strip().upper())
        return m.group(1) if m else None
    if entity_type == OFFICIAL:
        v = raw.strip().upper()
        return v if OFFICIAL_RE.match(v) else None
    if entity_type in (PERSON, ORG):
        n = normalise_name(raw)
        return n if len(n) >= 3 else None
    if entity_type == LOCATION:
        return re.sub(r"\s+", " ", raw.strip()).title() or None
    if entity_type == ID_DOCUMENT:
        return raw.strip().upper()
    return raw.strip() or None
