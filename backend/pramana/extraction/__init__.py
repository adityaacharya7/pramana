"""Extraction: evidence text -> proposed mentions with exact source spans.

Parsing is deterministic for a given parser version, so relations are not
stored separately: they are re-read from the (hash-verified) file whenever
the confirmed mentions of that file change.
"""
from __future__ import annotations

from .structured import parse_csv
from .narrative import parse_narrative
from .types import Parsed


def parse_file(text: str, file_type: str, group: str, date_order: str = "DMY") -> Parsed:
    if file_type == "CSV":
        return parse_csv(text, group, date_order)
    return parse_narrative(text, group)
