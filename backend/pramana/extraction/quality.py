"""The four intake quality checks (F2), run before analysis:

  duplicate_statement         the same statement received more than once
  statement_date_gap          statements for one account leave days uncovered
  balance_does_not_reconcile  opening + inflows - outflows != closing, or the
                              running balance jumps between rows
  ambiguous_date_format       slash dates where day and month cannot be told apart
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .structured import parse_csv
from .types import StatementMeta

DUPLICATE, GAP, RECONCILE, AMBIGUOUS = (
    "duplicate_statement", "statement_date_gap", "balance_does_not_reconcile", "ambiguous_date_format",
)
LABELS = {
    DUPLICATE: "Duplicate statement",
    GAP: "Gap in statement dates",
    RECONCILE: "Balance does not reconcile",
    AMBIGUOUS: "Ambiguous date format",
}


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def statement_meta(text: str, group: str, date_order: str = "DMY") -> StatementMeta | None:
    try:
        parsed = parse_csv(text, group, date_order)
    except ValueError:
        return None
    return parsed.statement if parsed.schema == "statement" else None


def check(files: list[tuple[object, StatementMeta]]) -> list[dict]:
    """`files` pairs each evidence file (id, filename, source_group_id) with
    its parsed statement metadata. Returns issue dicts keyed for upsert."""
    issues: list[dict] = []

    for ev, meta in files:
        unexplained = round(meta.closing - (meta.opening + meta.inflows - meta.outflows), 2)
        if abs(unexplained) > 0.005 or meta.first_break_row is not None:
            issues.append({
                "check": RECONCILE, "key": ev.id, "file_ids": [ev.id],
                "detail": {"account": meta.account, "filename": ev.filename, "period": [meta.start, meta.end],
                           "opening": meta.opening, "inflows": meta.inflows, "outflows": meta.outflows,
                           "closing": meta.closing, "unexplained_difference": unexplained,
                           "first_break_row": meta.first_break_row},
            })
        if meta.date_ambiguous:
            issues.append({
                "check": AMBIGUOUS, "key": ev.id, "file_ids": [ev.id],
                "detail": {"account": meta.account, "filename": ev.filename,
                           "note": "Every date has day and month of 12 or less, so DD/MM and MM/DD both parse. "
                                   "Read as DD/MM until an officer confirms the reading."},
            })

    by_group: dict[str, list] = defaultdict(list)
    for ev, meta in files:
        by_group[ev.source_group_id].append((ev, meta))
    for group, members in by_group.items():
        if len(members) > 1:
            issues.append({
                "check": DUPLICATE, "key": group, "file_ids": [ev.id for ev, _ in members],
                "detail": {"account": members[0][1].account, "filenames": [ev.filename for ev, _ in members],
                           "note": "Byte-identical copies. They are one source and are never counted as "
                                   "independent corroboration."},
            })

    by_account: dict[str, list] = defaultdict(list)
    for group, members in by_group.items():
        ev, meta = members[0]
        by_account[meta.account].append((ev, meta))
    for account, stmts in by_account.items():
        stmts.sort(key=lambda x: _dt(x[1].start))
        for (ev_a, a), (ev_b, b) in zip(stmts, stmts[1:]):
            gap_from = _dt(a.end) + timedelta(seconds=1)
            gap_to = _dt(b.start) - timedelta(seconds=1)
            if gap_to - gap_from >= timedelta(days=1):
                issues.append({
                    "check": GAP, "key": f"{account}:{a.end}:{b.start}", "file_ids": [ev_a.id, ev_b.id],
                    "detail": {"account": account, "missing_from": gap_from.isoformat(),
                               "missing_to": gap_to.isoformat(), "filenames": [ev_a.filename, ev_b.filename],
                               "note": "No statement covers these dates. Money may have moved in the gap: absence "
                                       "of a transaction there is not evidence that none occurred."},
                })
    return issues
