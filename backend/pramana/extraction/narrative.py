"""Narrative evidence: complaints, statements, chat exports.

Three layers, highest priority first when spans overlap:
  1. regex-v1    identifiers (account, IFSC, UPI, wallet, masked ID, phone, IMEI)
  2. pattern-v1  people named in a stated role ("I, <name>,", "account name
                 <name>", "Beneficiary name:", "Name:", honorifics, the
                 Hinglish and Hindi forms of the same)
  3. spaCy NER   remaining people, organisations and places

spaCy alone misreads many Indian names (it tagged "Sandeep" as a place in
testing), which is why the pattern layer exists and wins over it. spaCy is
optional: without it, layers 1 and 2 still run.

Relations are read from the same text so they can be re-derived at any
time; each one names the sentence that states it.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .identifiers import (
    AADHAAR_MASKED_RE, ACCOUNT, ACCOUNT_RE, BRANCH, ID_DOCUMENT, IFSC_RE, IMEI, IMEI_RE, LOCATION, ORG, PERSON,
    PHONE, PHONE_RE, UPI, UPI_RE, WALLET, WALLET_RE, canonical, luhn_ok,
)
from .types import Mention, Parsed, Relation

REGEX, PATTERN = "regex-v1", "pattern-v1"
PRIORITY = {REGEX: 0, PATTERN: 1}

NAME = r"((?:[A-Z][a-z]+|[A-Z]\.?)(?:[ ](?:[A-Z][a-z]+|[A-Z]\.?)){1,4})"
PRINCIPAL_PATTERNS = [
    rf"\bI,\s+{NAME}\s*,",
    rf"\bI am {NAME}\b",
    rf"\bMain {NAME}, umar",
    rf"मैं {NAME}, उम्र",
    rf"(?m)^Name:\s*{NAME}",
    rf"\bStatement of {NAME}\b",
    rf"mobile phone of {NAME}\b",
]
OTHER_PATTERNS = [
    rf"\b(?:Mr|Mrs|Ms|Smt|Shri|Dr)\.?\s+{NAME}",
    rf"\b(?:Inspector|Insp\.|DCP|ACP|SI|Sub-Inspector)\s+{NAME}",
    rf"\b(?:named|calling himself|calling herself|called himself|called herself|calls himself)\s+{NAME}",
    rf"\baccount name\s+{NAME}",
    rf"\bin the name of\s+{NAME}",
    rf"\bBeneficiary name:\s*{NAME}",
    rf"\bnaam\s+{NAME}",
    rf"खाताधारक\s+{NAME}",
    rf"ऑफिसर\s+{NAME}",
    rf"\bS/o\s+{NAME}",
    rf"\bmy (?:son|brother|husband|wife|daughter|neighbour)\s+(?:Mr\.\s+|Smt\.\s+)?{NAME}",
    rf"\bby my son\s+{NAME}",
    rf"(?m)^\d\d/\d\d/\d\d, [^-]+ - {NAME}:",
    r'Chat with: "([^"]+)"',
]
SIGNATURE_LINE = re.compile(rf"(?m)^{NAME}\s*$")
UPI_OWNER = re.compile(rf"\s*\({NAME}\)")

STOP = {
    "aadhaar", "whatsapp", "skype", "telegram", "imps", "neft", "rtgs", "upi", "otp", "pan", "kyc", "ifsc", "rs",
    "sir", "madam", "subject", "date", "reference", "sms", "instagram", "youtube", "google maps", "sub", "fir",
    "respected sir", "read", "usdt", "trc20", "police", "officer in charge", "the officer", "the senior inspector",
    "the station house officer", "the police inspector", "cyber police station", "crore", "id",
    "sim", "smt", "house", "utr", "beneficiary", "seller", "west region", "east region", "chat", "wallet",
    "arrest warrant", "digital arrest", "money laundering", "cyber crime",
}
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
ADDRESS_TAIL = re.compile(r"\b(?:chs|apartments?|residency|enclave|complex|society|nagar|sector)\b", re.IGNORECASE)
ABBREV_END = re.compile(r"(?:\b(?:Rs|No|no|Mr|Mrs|Ms|Smt|Dr|Insp|Sr|St|Prof|vs|Ltd|Pvt)\.|\b[A-Z]\.)$")
# Common Hinglish function words: when they are frequent the text is
# romanised Hindi, and the English NER model is not run on it.
HINGLISH = re.compile(r"\b(?:hai|hain|mein|ko|ki|ke|nahi|aur|maine|kaha|tha|thi|par|se|bhi|diya|gaya)\b", re.IGNORECASE)
PAYMENT_WORDS = re.compile(r"transferred|paid|sent|debited|transfer|bheje|kat gaye|भेजे|कट गए|pay\b", re.IGNORECASE)
CALL_WORDS = re.compile(r"\bcall|message|\bsms\b|फोन|whatsapp", re.IGNORECASE)
MY_ACCOUNT = re.compile(r"(?:\bmy\b[^.\n]{0,40}\baccount|mera account|मेरा खाता|account is)", re.IGNORECASE)
MOBILE_CTX = re.compile(r"(?:mobile(?: number| no\.?)?(?: is)?|मोबाइल नंबर|own number)[\s:]*(?:\+?91[\s-]?)?$", re.IGNORECASE)
SKIP_NUMBER_CTX = re.compile(r"(?:reference|ref|utr|acknowledgement|txid|रेफरेंस|पावती|ack)[^\d\n]{0,25}$", re.IGNORECASE)
AMOUNT = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)")


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
        return nlp, f"spacy-en_core_web_sm-{nlp.meta['version']}"
    except Exception:  # spaCy or its model not installed: rules only
        return None, None


def spacy_version() -> str | None:
    return _nlp()[1]


def identifier_mentions(text: str, record: str) -> list[Mention]:
    out: list[Mention] = []

    def add(m: re.Match, etype: str, group: int = 1):
        raw = m.group(group)
        value = canonical(etype, raw)
        if value:
            out.append(Mention(m.start(group), m.end(group), etype, value, raw, REGEX, record))

    for m in ACCOUNT_RE.finditer(text):
        add(m, ACCOUNT)
    for m in IFSC_RE.finditer(text):
        add(m, BRANCH)
    for m in UPI_RE.finditer(text):
        add(m, UPI)
    for m in WALLET_RE.finditer(text):
        add(m, WALLET)
    for m in AADHAAR_MASKED_RE.finditer(text):
        add(m, ID_DOCUMENT)
    for m in PHONE_RE.finditer(text):
        if SKIP_NUMBER_CTX.search(text[max(0, m.start() - 40):m.start()]):
            continue
        add(m, PHONE)
    for m in IMEI_RE.finditer(text):
        if re.search(r"imei", text[max(0, m.start() - 20):m.start()], re.IGNORECASE) and luhn_ok(m.group(1)):
            add(m, IMEI)
    return out


def _person_mentions(text: str, record: str) -> list[Mention]:
    out: list[Mention] = []

    def add(start: int, end: int, role: str | None, etype: str = PERSON):
        raw = text[start:end]
        value = canonical(etype, raw)
        if value and value.lower() not in STOP and len(value.split()) >= 1:
            out.append(Mention(start, end, etype, value, raw, PATTERN, record, role))

    for pat in PRINCIPAL_PATTERNS:
        for m in re.finditer(pat, text):
            add(m.start(1), m.end(1), "principal")
    for pat in OTHER_PATTERNS:
        for m in re.finditer(pat, text):
            add(m.start(1), m.end(1), None)
    for m in UPI_RE.finditer(text):
        owner = UPI_OWNER.match(text, m.end())
        if owner:
            add(owner.start(1), owner.end(1), None)
    for m in SIGNATURE_LINE.finditer(text):
        if len(m.group(1).split()) >= 2:
            add(m.start(1), m.end(1), "signature")
    return out


def _spacy_mentions(text: str, record: str) -> tuple[list[Mention], str | None]:
    nlp, version = _nlp()
    if nlp is None:
        return [], None
    words = max(1, len(text.split()))
    if len(HINGLISH.findall(text)) / words > 0.06 or len(DEVANAGARI.findall(text)) > len(text) * 0.2:
        return [], None  # romanised or Devanagari Hindi: the English model only adds noise
    out = []
    labels = {"PERSON": PERSON, "ORG": ORG, "GPE": LOCATION, "LOC": LOCATION}
    for ent in nlp(text).ents:
        etype = labels.get(ent.label_)
        raw = ent.text.strip()
        if not etype or len(raw) < 3 or any(ch.isdigit() for ch in raw) or "\n" in raw:
            continue
        if raw.lower() in STOP or raw.lower().removeprefix("the ") in STOP:
            continue
        # Devanagari text, lone surnames and address fragments are where the
        # English model goes wrong; the rule layers cover those cases.
        if DEVANAGARI.search(raw) or "(" in raw or ADDRESS_TAIL.search(raw):
            continue
        if etype == PERSON and len(raw.split()) < 2:
            continue
        value = canonical(etype, raw)
        if value:
            start = ent.start_char + (len(ent.text) - len(ent.text.lstrip()))
            out.append(Mention(start, start + len(raw), etype, value, raw, version, record))
    return out, version


def _resolve(candidates: list[Mention]) -> list[Mention]:
    """Keep the highest-priority mention where spans overlap."""
    ranked = sorted(candidates, key=lambda m: (PRIORITY.get(m.extractor, 2), -(m.end - m.start), m.start))
    kept: list[Mention] = []
    for m in ranked:
        if all(m.end <= k.start or m.start >= k.end for k in kept):
            kept.append(m)
    return sorted(kept, key=lambda m: m.start)


def _sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"(?<=[.!?।])\s+|\n", text):
        gap = text[m.start():m.end()]
        if "\n" not in gap and ABBREV_END.search(text[max(0, m.start() - 8):m.start()]):
            continue  # "Rs. 78,000", "Mr. Sharma", "A. Kulkarni" do not end a sentence
        if m.start() > start:
            spans.append((start, m.start()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _compatible(a: str, b: str) -> bool:
    """Same person written two ways inside one record ("Shobha A. Kulkarni" /
    "Shobha Anant Kulkarni")."""
    ta, tb = a.lower().replace(".", "").split(), b.lower().replace(".", "").split()
    if not ta or not tb or ta[-1] != tb[-1] or ta[0] != tb[0]:
        return False
    # The abbreviated form is the one with fewer words, or with the same
    # number of words but shorter ones ("Shobha A. Kulkarni").
    short, long_ = sorted((ta, tb), key=lambda t: (len(t), sum(map(len, t))))
    j = 0
    for tok in long_:
        if j < len(short) and (tok == short[j] or (len(short[j]) == 1 and tok.startswith(short[j]))):
            j += 1
    return j == len(short)


def parse_narrative(text: str, group: str) -> Parsed:
    record = group
    spacy_found, version = _spacy_mentions(text, record)
    mentions = _resolve(identifier_mentions(text, record) + _person_mentions(text, record) + spacy_found)
    out = Parsed(schema="narrative", mentions=mentions,
                 extractors=[REGEX, PATTERN] + ([version] if version else []))

    sentences = _sentences(text)

    def sentence_of(pos: int) -> tuple[int, int]:
        for s, e in sentences:
            if s <= pos < e:
                return (s, e)
        return (pos, pos)

    def rel(src: Mention, dst: Mention, rtype: str, anchor: int, **attrs):
        out.relations.append(Relation(src.span, dst.span, rtype, sentence_of(anchor), group, attrs))

    persons = [m for m in mentions if m.type in (PERSON, ORG)]
    principal = next((m for m in persons if m.role == "principal"), None)
    accounts = [m for m in mentions if m.type in (ACCOUNT, UPI)]
    phones = [m for m in mentions if m.type == PHONE]

    principal_phone = None
    principal_accounts: list[Mention] = []
    if principal:
        for p in phones:
            if MOBILE_CTX.search(text[max(0, p.start - 30):p.start]):
                principal_phone = p
                rel(principal, p, "uses", p.start, basis="own number stated")
                break
        for a in accounts:
            if a.type == ACCOUNT and MY_ACCOUNT.search(text[max(0, a.start - 60):a.start]):
                principal_accounts.append(a)
                rel(principal, a, "owns", a.start, basis="complainant's own account")
        for d in (m for m in mentions if m.type == ID_DOCUMENT):
            rel(principal, d, "attr:id_document", d.start, kind="Aadhaar")

    # Beneficiary names: "account name X", "in the name of X", "(X)" after a UPI ID ...
    for p in persons:
        if p.extractor != PATTERN:
            continue
        before = text[max(0, p.start - 25):p.start]
        upi_before = next((a for a in accounts if a.type == UPI and 0 <= p.start - a.end <= 2
                           and before.endswith("(")), None)
        if upi_before:
            rel(p, upi_before, "owns", p.start, basis="named with the UPI ID in the complaint")
            continue
        if not re.search(r"account name|in the name of|beneficiary name|naam|खाताधारक", before.lower()):
            continue
        s, e = sentence_of(p.start)
        # The account may sit on the line before or after ("Beneficiary name:"
        # then "Account no.:").
        near = [a for a in accounts if a not in principal_accounts and s - 200 <= a.start <= e + 120]
        if near:
            target = min(near, key=lambda a: abs(a.start - p.start))
            rel(p, target, "owns", p.start, basis="named as account holder in the complaint")

    # Account + IFSC in one sentence: the account is held at that branch.
    for b in (m for m in mentions if m.type == BRANCH):
        s, e = sentence_of(b.start)
        near = [a for a in accounts if a.type == ACCOUNT and s <= a.start < e and a not in principal_accounts]
        if near:
            rel(min(near, key=lambda a: abs(a.start - b.start)), b, "opened_at", b.start, basis="IFSC stated with account")

    # Calls and messages to the complainant.
    if principal_phone:
        for p in phones:
            if p is principal_phone:
                continue
            s, e = sentence_of(p.start)
            if CALL_WORDS.search(text[s:e]):
                rel(p, principal_phone, "called", p.start, basis="complainant reports contact from this number")

    # Payments from the complainant's account.
    if principal_accounts:
        source = principal_accounts[0]
        last_beneficiary = None
        for s, e in sentences:
            in_sentence = [a for a in accounts if s <= a.start < e]
            others = [a for a in in_sentence if a not in principal_accounts]
            if others:
                last_beneficiary = others[-1]
            if not PAYMENT_WORDS.search(text[s:e]):
                continue
            amt = AMOUNT.search(text[s:e])
            amount = float(amt.group(1).replace(",", "")) if amt else None
            targets = others
            if not targets and any(a in principal_accounts for a in in_sentence):
                # "I transferred Rs. X from my account A" with the beneficiary
                # given just before or just after that sentence.
                following = [a for a in accounts if e <= a.start <= e + 300 and a not in principal_accounts]
                fallback = last_beneficiary or (following[0] if following else None)
                targets = [fallback] if fallback else []
            for t in targets:
                out.relations.append(Relation(source.span, t.span, "transferred", (s, e), group,
                                              {"amount": amount, "basis": "complainant's account of the payment"}))

    # Chat exports: "Chat with: "X" (+91 N)" and "Seller's own number".
    for m in re.finditer(r'Chat with: "([^"]+)" \(', text):
        who = next((x for x in persons if x.start == m.start(1)), None)
        num = next((p for p in phones if m.end() <= p.start <= m.end() + 6), None)
        if who and num:
            rel(who, num, "uses", m.start(), basis="chat contact number")
    return out
