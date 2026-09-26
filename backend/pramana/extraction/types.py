from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Span = tuple[int, int]


@dataclass
class Mention:
    start: int
    end: int
    type: str
    value: str  # canonical value
    text: str  # exact source text
    extractor: str
    record_key: str
    role: str | None = None  # e.g. "principal" (complainant / witness / KYC holder)

    @property
    def span(self) -> Span:
        return (self.start, self.end)


@dataclass
class Relation:
    """A relationship the source states between two mentions. It only becomes
    a graph edge once both mentions are confirmed by an officer."""
    src: Span
    dst: Span
    type: str
    support: Span  # the row or sentence that states it
    group: str  # source group: records sharing a group count as one source
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttrUpdate:
    target: Span
    attrs: dict[str, Any]


@dataclass
class TxnRow:
    row_number: int
    span: Span
    ts: str
    ts_ambiguous: bool
    own_span: Span
    counterparty_span: Span | None
    counterparty_raw: str
    counterparty_name: str
    direction: str  # "in" | "out"
    amount: float
    channel: str
    reference: str
    description: str


@dataclass
class CallRow:
    span: Span
    ts: str
    kind: str
    a: Span  # caller
    b: Span  # receiver
    duration: int


@dataclass
class StatementMeta:
    account: str
    start: str
    end: str
    opening: float
    closing: float
    inflows: float
    outflows: float
    first_break_row: int | None
    date_style: str  # iso | slash
    date_ambiguous: bool


@dataclass
class Parsed:
    schema: str  # statement | kyc | cdr | narrative | table
    mentions: list[Mention] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    attrs: list[AttrUpdate] = field(default_factory=list)
    txns: list[TxnRow] = field(default_factory=list)
    calls: list[CallRow] = field(default_factory=list)
    statement: StatementMeta | None = None
    extractors: list[str] = field(default_factory=list)
