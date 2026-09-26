"""Spreadsheet evidence: bank statements, account-opening (KYC) responses and
call detail records. Columns carry their meaning, so these are read by column
rather than guessed at."""
from __future__ import annotations

import re
from datetime import datetime

from . import csvspan
from .identifiers import (
    ACCOUNT, BRANCH, ID_DOCUMENT, IMEI, OFFICIAL, ORG, PERSON, PHONE, UPI, canonical,
)
from .narrative import identifier_mentions
from .types import AttrUpdate, CallRow, Mention, Parsed, Relation, StatementMeta, TxnRow

CSV = "csv-v1"
IST = "+05:30"

STATEMENT_COLS = {"account_no", "txn_time", "debit", "credit", "balance"}
KYC_COLS = {"account_no", "holder_name", "opening_official_id"}
CDR_COLS = {"target_number", "other_number", "call_type"}


def detect_schema(header: list[str]) -> str:
    h = set(header)
    if STATEMENT_COLS <= h:
        return "statement"
    if KYC_COLS <= h:
        return "kyc"
    if CDR_COLS <= h:
        return "cdr"
    return "table"


def _money(s: str) -> float:
    s = (s or "").replace(",", "").strip()
    return float(s) if s else 0.0


SLASH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$")


def slash_ambiguity(values: list[str]) -> tuple[bool, bool]:
    """(uses_slash_dates, ambiguous). Ambiguous when no value can only be
    read one way (every first and second component is 12 or less)."""
    parsed = [SLASH_RE.match(v.strip()) for v in values if v.strip()]
    parsed = [m for m in parsed if m]
    if not parsed:
        return False, False
    return True, all(int(m.group(1)) <= 12 and int(m.group(2)) <= 12 for m in parsed)


def parse_time(value: str, order: str = "DMY") -> str:
    v = value.strip()
    m = SLASH_RE.match(v)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        day, month = (a, b) if order == "DMY" else (b, a)
        if a > 12:
            day, month = a, b
        elif b > 12:
            day, month = b, a
        hh, mm, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
        return datetime(y, month, day, hh, mm, ss).isoformat() + IST
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).isoformat() + IST
        except ValueError:
            pass
    raise ValueError(f"unrecognised date/time {value!r}")


def _mention(out: Parsed, cell: csvspan.Cell, etype: str, record: str, role: str | None = None,
             start: int | None = None, text: str | None = None) -> Mention | None:
    raw = text if text is not None else cell.value
    s = start if start is not None else cell.start
    lead = len(raw) - len(raw.lstrip())
    raw_clean = raw.strip()
    if not raw_clean:
        return None
    value = canonical(etype, raw_clean)
    if not value:
        return None
    m = Mention(s + lead, s + lead + len(raw_clean), etype, value, raw_clean, CSV, record, role)
    out.mentions.append(m)
    return m


def _counterparty_type(value: str) -> str | None:
    v = value.strip()
    if "@" in v:
        return UPI
    if v.isdigit() and 9 <= len(v) <= 18:
        return ACCOUNT
    return None


def parse_statement(text: str, rows: list[tuple[csvspan.Row, dict]], group: str, date_order: str) -> Parsed:
    out = Parsed(schema="statement", extractors=[CSV])
    if not rows:
        return out
    uses_slash, ambiguous = slash_ambiguity([c["txn_time"].value for _, c in rows if "txn_time" in c])
    first_row, first = rows[0]
    last_row, last = rows[-1]
    own = _mention(out, first["account_no"], ACCOUNT, f"{group}:stmt", role="statement_account")
    if own is None:
        return out
    opening = _money(first["balance"].value) if "OPENING" in first["description"].value.upper() else 0.0
    closing = _money(last["balance"].value) if "CLOSING" in last["description"].value.upper() else 0.0
    inflows = outflows = 0.0
    running = opening
    first_break = None
    for r, c in rows:
        desc = c.get("description").value if c.get("description") else ""
        if "OPENING BALANCE" in desc.upper() or "CLOSING BALANCE" in desc.upper():
            continue
        debit, credit = _money(c["debit"].value), _money(c["credit"].value)
        inflows += credit
        outflows += debit
        running = round(running + credit - debit, 2)
        bal = c["balance"].value.strip()
        if first_break is None and bal and abs(_money(bal) - running) > 0.005:
            first_break = r.index
            running = _money(bal)  # continue from the stated balance
        cp_cell = c.get("counterparty_account")
        cp_raw = cp_cell.value.strip() if cp_cell else ""
        cp_type = _counterparty_type(cp_raw) if cp_raw else None
        cp = _mention(out, cp_cell, cp_type, f"{group}:r{r.index}") if cp_type else None
        ref = c["reference"].value.strip() if c.get("reference") else ""
        ts = parse_time(c["txn_time"].value, date_order)
        direction = "in" if credit > 0 else "out"
        amount = credit if credit > 0 else debit
        out.txns.append(TxnRow(
            row_number=r.index, span=(r.start, r.end), ts=ts, ts_ambiguous=ambiguous, own_span=own.span,
            counterparty_span=cp.span if cp else None, counterparty_raw=cp_raw,
            counterparty_name=c["counterparty_name"].value.strip() if c.get("counterparty_name") else "",
            direction=direction, amount=amount, channel=c["channel"].value.strip() if c.get("channel") else "",
            reference=ref, description=desc,
        ))
        if cp:
            src, dst = (cp.span, own.span) if direction == "in" else (own.span, cp.span)
            # Both statements of one transfer carry the same bank reference:
            # two views of one bank record, so one source group.
            out.relations.append(Relation(src, dst, "transferred", (r.start, r.end),
                                          f"bankref:{ref}" if ref else f"{group}:r{r.index}",
                                          {"amount": amount, "ts": ts, "reference": ref,
                                           "channel": c["channel"].value.strip() if c.get("channel") else ""}))
        if cp and c.get("counterparty_name") and c["counterparty_name"].value.strip():
            out.attrs.append(AttrUpdate(cp.span, {"names_seen": [c["counterparty_name"].value.strip()]}))
    out.statement = StatementMeta(
        account=own.value, start=parse_time(first["txn_time"].value, date_order),
        end=parse_time(last["txn_time"].value, date_order), opening=opening, closing=closing,
        inflows=round(inflows, 2), outflows=round(outflows, 2), first_break_row=first_break,
        date_style="slash" if uses_slash else "iso", date_ambiguous=ambiguous,
    )
    return out


def _split_cell(cell: csvspan.Cell, sep: str = ";"):
    pos = 0
    for part in cell.value.split(sep):
        yield cell.start + pos, part
        pos += len(part) + len(sep)


def parse_kyc(rows, group: str) -> Parsed:
    out = Parsed(schema="kyc", extractors=[CSV])
    for r, c in rows:
        rec = f"{group}:r{r.index}"
        support = (r.start, r.end)
        g = f"{group}:r{r.index}"
        acct = _mention(out, c["account_no"], ACCOUNT, rec)
        if acct is None:
            continue
        holder_type = c.get("holder_type").value.strip() if c.get("holder_type") else "Individual"
        holder = _mention(out, c["holder_name"], PERSON if holder_type.lower() == "individual" else ORG, rec,
                          role="principal")
        if holder:
            out.relations.append(Relation(holder.span, acct.span, "owns", support, g, {"basis": "account holder"}))
            person_attrs = {k: c[k].value.strip() for k in ("father_or_spouse_name", "date_of_birth", "address")
                            if c.get(k) and c[k].value.strip()}
            if person_attrs:
                out.attrs.append(AttrUpdate(holder.span, person_attrs))
        if c.get("authorised_signatories"):
            for start, part in _split_cell(c["authorised_signatories"]):
                sig = _mention(out, c["authorised_signatories"], PERSON, rec, start=start, text=part)
                if sig:
                    out.relations.append(Relation(sig.span, acct.span, "owns", support, g,
                                                  {"basis": "authorised signatory"}))
        if c.get("registered_mobile"):
            ph = _mention(out, c["registered_mobile"], PHONE, rec)
            if ph:
                out.relations.append(Relation(ph.span, acct.span, "registered_to", support, g,
                                              {"basis": "registered mobile"}))
        if c.get("ifsc"):
            br = _mention(out, c["ifsc"], BRANCH, rec)
            if br:
                out.relations.append(Relation(acct.span, br.span, "opened_at", support, g))
                out.attrs.append(AttrUpdate(br.span, {k: c[k].value.strip() for k in ("branch_code", "branch_name")
                                                      if c.get(k)}))
        if c.get("opening_official_id"):
            off = _mention(out, c["opening_official_id"], OFFICIAL, rec)
            if off:
                out.relations.append(Relation(acct.span, off.span, "opened_by", support, g))
                attrs = {"name": c["opening_official_name"].value.strip()} if c.get("opening_official_name") else {}
                if c.get("branch_code"):
                    attrs["branch_code"] = c["branch_code"].value.strip()
                out.attrs.append(AttrUpdate(off.span, attrs))
        if c.get("linked_upi_ids") and c["linked_upi_ids"].value.strip():
            for start, part in _split_cell(c["linked_upi_ids"]):
                u = _mention(out, c["linked_upi_ids"], UPI, rec, start=start, text=part)
                if u:
                    out.relations.append(Relation(u.span, acct.span, "registered_to", support, g,
                                                  {"basis": "linked UPI ID"}))
        if holder and c.get("id_document_masked") and c["id_document_masked"].value.strip():
            doc = _mention(out, c["id_document_masked"], ID_DOCUMENT, rec)
            if doc:
                kind = c["id_document_type"].value.strip() if c.get("id_document_type") else "ID"
                out.relations.append(Relation(holder.span, doc.span, "attr:id_document", support, g, {"kind": kind}))
        kyc = {k: c[k].value.strip() for k in ("account_type", "holder_type", "opening_date", "branch_code",
                                               "kyc_doc_sha256", "device_id_at_opening", "nominee")
               if c.get(k) and c[k].value.strip()}
        out.attrs.append(AttrUpdate(acct.span, {"kyc": kyc}))
    return out


def parse_cdr(rows, group: str) -> Parsed:
    out = Parsed(schema="cdr", extractors=[CSV])
    for r, c in rows:
        rec = f"{group}:r{r.index}"
        g = f"{group}:r{r.index}"
        support = (r.start, r.end)
        target = _mention(out, c["target_number"], PHONE, rec, role="cdr_target")
        other = _mention(out, c["other_number"], PHONE, rec)
        if target is None or other is None:
            continue
        kind = c["call_type"].value.strip().upper()
        a, b = (other, target) if kind in ("MTC", "SMS-MT") else (target, other)
        ts = parse_time(c["start_time"].value) if c.get("start_time") else ""
        dur = int(c["duration_sec"].value or 0) if c.get("duration_sec") and c["duration_sec"].value.isdigit() else 0
        out.relations.append(Relation(a.span, b.span, "called", support, g, {"kind": kind, "ts": ts, "duration": dur}))
        out.calls.append(CallRow(support, ts, kind, a.span, b.span, dur))
        if c.get("imei") and c["imei"].value.strip():
            im = _mention(out, c["imei"], IMEI, rec)
            if im:
                out.relations.append(Relation(target.span, im.span, "uses", support, g, {"basis": "handset in CDR"}))
    return out


def parse_table(text: str, group: str) -> Parsed:
    out = Parsed(schema="table", extractors=["regex-v1"])
    out.mentions = identifier_mentions(text, f"{group}:table")
    return out


def parse_csv(text: str, group: str, date_order: str = "DMY") -> Parsed:
    rows = csvspan.parse(text)
    header, data = csvspan.as_dicts(rows)
    schema = detect_schema(header)
    if schema == "statement":
        return parse_statement(text, data, group, date_order)
    if schema == "kyc":
        return parse_kyc(data, group)
    if schema == "cdr":
        return parse_cdr(data, group)
    return parse_table(text, group)
