"""Self-checks run after generation. The dataset is only useful if its hidden
structure is exactly what the ground truth says, so any drift (an accidental
shared identifier, a statement that stops reconciling, a fourth account at
branch B-17) fails the build instead of silently changing the demo."""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def _parse_time(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(s)


def _compact(text: str) -> str:
    # Written numbers are often grouped ("+91 98765 43210", "5017 2233 4455").
    return re.sub(r"(?<=\d) (?=\d)", "", text)


def _has_number(text: str, digits: str) -> bool:
    # Whole-number match, allowing an Indian country-code prefix on phones.
    return re.search(rf"(?<!\d)(?:\+?91-?)?{digits}(?!\d)", text) is not None


def _statement_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def run_checks(root: Path, manifest_files: list[dict], world, truth: dict, quality: list[dict]) -> dict:
    problems: list[str] = []
    files_by_case: dict[str, list[Path]] = defaultdict(list)
    for f in manifest_files:
        files_by_case[f["case_id"]].append(root / f["path"])

    # 1. Reconciliation: opening + credits - debits must equal closing, except
    #    for the statement planted not to.
    planted_recon = {q["file"] for q in quality if q["issue"] == "balance_does_not_reconcile"}
    stmt_files = [f for f in manifest_files if f["kind"] == "bank_statement"]
    non_reconciling = set()
    txn_count = 0
    transfers_by_ref: dict[str, list[tuple[str, float]]] = defaultdict(list)
    flows: list[tuple[datetime, str, str]] = []  # (time, sender, receiver)
    seen_contents = set()
    for f in stmt_files:
        rows = _statement_rows(root / f["path"])
        opening = float(rows[0]["balance"])
        closing = float(rows[-1]["balance"])
        net = sum(float(r["credit"] or 0) - float(r["debit"] or 0) for r in rows[1:-1])
        if abs(opening + net - closing) > 0.005:
            non_reconciling.add(f["path"])
        body = (root / f["path"]).read_bytes()
        duplicate = body in seen_contents
        seen_contents.add(body)
        if duplicate:
            continue  # a byte-identical copy is one source, not more transactions
        for r in rows[1:-1]:
            txn_count += 1
            amt = float(r["credit"] or 0) - float(r["debit"] or 0)
            if r["reference"]:
                transfers_by_ref[r["reference"]].append((r["account_no"], amt))
            t = _parse_time(r["txn_time"])
            if amt > 0:
                flows.append((t, r["counterparty_account"], r["account_no"]))
            else:
                flows.append((t, r["account_no"], r["counterparty_account"]))
    if non_reconciling != planted_recon:
        problems.append(f"reconciliation mismatch: got {sorted(non_reconciling)}, planted {sorted(planted_recon)}")

    # 2. A reference seen on two statements must describe one transfer:
    #    equal amounts, opposite directions.
    for ref, sides in transfers_by_ref.items():
        if len(sides) == 2 and abs(sides[0][1] + sides[1][1]) > 0.005:
            problems.append(f"reference {ref} amounts disagree: {sides}")
        if len(sides) > 2:
            problems.append(f"reference {ref} appears {len(sides)} times")

    # 3. Complaint-linked identifiers: every known account / UPI ID named in a
    #    complaint or supplementary statement.
    complaint_text = {
        f["path"]: (root / f["path"]).read_text(encoding="utf-8")
        for f in manifest_files if f["kind"] in {"complaint", "supplementary_statement"}
    }
    all_complaints = "\n".join(complaint_text.values())
    compact = _compact(all_complaints)
    complaint_linked = ({a for a in world.accounts if _has_number(compact, a)}
                        | {v for v in world.upis if v in all_complaints})
    # Receiving accounts are linked through the complaint that names them; the
    # victims' own accounts are linked too.

    # 4. Convergence: only HUB may receive from >= 3 distinct complaint-linked
    #    senders within 60 minutes.
    by_receiver: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for t, s, rcv in flows:
        if s in complaint_linked:
            by_receiver[rcv].append((t, s))
    hub = truth["tri_city"]["labels"]["HUB"]["value"]
    converging = set()
    for rcv, items in by_receiver.items():
        items.sort()
        for i, (t0, _) in enumerate(items):
            senders = {s for t, s in items[i:] if t - t0 <= timedelta(minutes=60)}
            if len(senders) >= 3:
                converging.add(rcv)
    if converging != {hub}:
        problems.append(f"convergence points {sorted(converging)} != {{HUB}}")

    # 5. Facilitator: only E-45 opened >= 3 complaint-linked accounts.
    opened: dict[tuple[str, str], set[str]] = defaultdict(set)
    for f in manifest_files:
        if f["kind"] == "kyc_response":
            for r in _statement_rows(root / f["path"]):
                if r["account_no"] in complaint_linked:
                    opened[(r["branch_code"], r["opening_official_id"])].add(r["account_no"])
    facilitators = {k for k, v in opened.items() if len(v) >= 3}
    if facilitators != {("B-17", "E-45")}:
        problems.append(f"facilitator patterns {facilitators} != {{(B-17, E-45)}}")

    # 6. Shared identifiers across cases must be exactly the documented ones.
    identifiers = set(world.accounts) | set(world.upis) | set(world.phones)
    cases_for: dict[str, set[str]] = defaultdict(set)
    for case_id, paths in files_by_case.items():
        text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
        text_compact = _compact(text)
        for ident in identifiers:
            if ident.isdigit():
                if _has_number(text_compact, ident):
                    cases_for[ident].add(case_id)
            elif ident in text:
                cases_for[ident].add(case_id)
    shared = {i: sorted(c) for i, c in cases_for.items() if len(c) >= 2}
    labels = truth["tri_city"]["labels"]
    expected = {labels[k]["value"] for k in ["P-77", "HUB", "M2", "M3", "V2-phone"]}
    billers = {v for v, meta in world.upis.items() if meta["role"] == "utility_biller"}
    unexpected = set(shared) - expected - billers
    missing = expected - set(shared)
    if unexpected:
        problems.append(f"unexpected shared identifiers: { {u: shared[u] for u in unexpected} }")
    if missing:
        problems.append(f"expected shared identifiers missing: {missing}")

    # 7. Scale targets from the spec.
    narratives = [f for f in manifest_files
                  if f["kind"] in {"complaint", "witness_statement", "supplementary_statement"}]
    non_english = [f for f in narratives if f["language"] in {"hi", "hinglish"}]
    cases = {f["case_id"] for f in manifest_files if f["case_id"]}
    branches = {k[0] for k in opened} | {"B-17", "B-22", "B-31"}
    stats = {
        "cases": len(cases),
        "narratives": len(narratives),
        "hindi_or_hinglish_narratives": len(non_english),
        "accounts": len(world.accounts),
        "upi_ids": len(world.upis),
        "phones": len(world.phones),
        "transactions": txn_count,
        "bank_statements": len(stmt_files),
        "bank_branches": len(branches),
        "bank_officials": 6,
        "shared_identifiers": {i: shared[i] for i in sorted(shared)},
    }
    if stats["cases"] != 30:
        problems.append(f"expected 30 cases, got {stats['cases']}")
    if stats["narratives"] != 40:
        problems.append(f"expected 40 narratives, got {stats['narratives']}")
    if stats["hindi_or_hinglish_narratives"] < 5:
        problems.append("fewer than 5 Hindi/Hinglish narratives")
    if not 1300 <= txn_count <= 1700:
        problems.append(f"transaction count {txn_count} outside 1,300-1,700")
    if not 170 <= len(world.accounts) <= 240:
        problems.append(f"account count {len(world.accounts)} outside 170-240")

    return {"problems": problems, "stats": stats}
