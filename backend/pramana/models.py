"""The MVP data model: the 20 tables of the spec ("Data model"), plus one
infrastructure row (``deployment``) recording which build owns the database.

Every analytical object points back to an evidence file (and, where it comes
from text, a character span). Only the Week 1 tables are written today;
the rest are defined now so the schema is stable while later features land.

Types are kept PostgreSQL-portable: string ids, JSON columns, Numeric money.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


Money = Numeric(14, 2)


class Deployment(Base):
    __tablename__ = "deployment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))
    dataset: Mapped[str | None] = mapped_column(String(64))


# --- people, cases, access -----------------------------------------------------

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # permissions.Role
    unit: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str | None] = mapped_column(String(128))
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    # Last accepted TOTP time-step: a code can be used once, never replayed.
    totp_last_step: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(40))


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    fir_no: Mapped[str] = mapped_column(String(32))
    unit: Mapped[str] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    title: Mapped[str] = mapped_column(String(200))
    station: Mapped[str | None] = mapped_column(String(200))
    registered_on: Mapped[str | None] = mapped_column(String(10))
    complainant: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40))


class CaseMember(Base):
    __tablename__ = "case_members"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    access: Mapped[str] = mapped_column(String(8))  # owner | member
    granted_at: Mapped[str] = mapped_column(String(40))
    granted_by: Mapped[str | None] = mapped_column(String(64))


class AccessRequest(Base):
    __tablename__ = "access_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    requester: Mapped[str] = mapped_column(ForeignKey("users.id"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))
    decided_at: Mapped[str | None] = mapped_column(String(40))


# --- evidence and extraction -----------------------------------------------------

class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(8))  # CSV | TXT | PDF
    kind: Mapped[str] = mapped_column(String(32), default="unclassified")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(512))  # relative to the evidence store
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[str] = mapped_column(String(40))
    integrity_status: Mapped[str] = mapped_column(String(16), default="OK")  # OK | MISMATCH | MISSING
    last_verified_at: Mapped[str | None] = mapped_column(String(40))
    # Byte-identical copies of one file share a group and count as one source.
    source_group_id: Mapped[str] = mapped_column(String(32))
    extracted_at: Mapped[str | None] = mapped_column(String(40))
    extractor_versions: Mapped[list[str] | None] = mapped_column(JSON)


class EvidenceBlob(Base):
    """Sealed bytes when there is no persistent disk (serverless hosts).
    Infrastructure, like ``deployment``: not one of the spec's 20 tables."""
    __tablename__ = "evidence_blobs"
    storage_path: Mapped[str] = mapped_column(String(512), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class Extraction(Base):
    __tablename__ = "extractions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"), index=True)
    span_start: Mapped[int] = mapped_column(Integer)
    span_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(32))
    proposed_value: Mapped[str | None] = mapped_column(String(255))
    extractor: Mapped[str] = mapped_column(String(64))  # e.g. regex-v1, pattern-v1, csv-v1, spacy-en_core_web_sm-3.8.0
    # The record a mention belongs to (a CSV row, or the whole narrative).
    # People are identified per record, never across records by name alone.
    record_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING | CONFIRMED | REJECTED
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[str | None] = mapped_column(String(40))


class Entity(Base):
    __tablename__ = "entities"
    # Identifiers (phone, account, UPI ...) are global: one number, one entity,
    # whichever case it appears in. People and organisations are scoped to the
    # record they come from (scope_key) and only joined by an identity decision.
    __table_args__ = (UniqueConstraint("type", "canonical_value", "scope_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(32))
    canonical_value: Mapped[str] = mapped_column(String(255))
    scope_key: Mapped[str] = mapped_column(String(80), default="")
    attrs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40))


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    extraction_id: Mapped[str] = mapped_column(ForeignKey("extractions.id"))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)


class IdentityDecision(Base):
    __tablename__ = "identity_decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entity_a: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    entity_b: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    decision: Mapped[str] = mapped_column(String(16))  # MERGE | SPLIT | KEEP_SEPARATE | UNRESOLVED
    reason: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[str] = mapped_column(String(40))


# --- graph and money -------------------------------------------------------------

class Edge(Base):
    __tablename__ = "edges"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    src: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    dst: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class EdgeSupport(Base):
    __tablename__ = "edge_support"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    edge_id: Mapped[str] = mapped_column(ForeignKey("edges.id"), index=True)
    evidence_file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"))
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    source_group_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))  # independent | duplicate_copy


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    from_acct: Mapped[str] = mapped_column(String(64), index=True)
    to_acct: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    ts: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str | None] = mapped_column(String(16))
    reference: Mapped[str | None] = mapped_column(String(64), index=True)
    evidence_file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(255))
    counterparty_name: Mapped[str | None] = mapped_column(String(255))
    # True when the timestamp came from an ambiguous DD/MM vs MM/DD format.
    ts_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)


class MOProfile(Base):
    __tablename__ = "mo_profiles"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(128))


# --- rules, leads, scenarios, drafts --------------------------------------------

class RuleRun(Base):
    __tablename__ = "rule_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(16))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    run_at: Mapped[str] = mapped_column(String(40))
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("scenarios.id"))
    case_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    run_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rule_run_id: Mapped[str] = mapped_column(ForeignKey("rule_runs.id"))
    observation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="DETECTED")
    owner: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))


class LeadSupport(Base):
    __tablename__ = "lead_support"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # support | conflict | unknown
    note: Mapped[str | None] = mapped_column(Text)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_hashes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    decisions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    operations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    rule_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attribution_method: Mapped[str | None] = mapped_column(String(16))
    software_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    expected_results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40))


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    base_snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"))
    # [{"op": "exclude_source" | "dispute_txn" | "simulate_no_txn", ...}]
    operations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    reconciles: Mapped[bool | None] = mapped_column(Boolean)
    result_diff: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="sandbox")  # sandbox | proposed | applied | rejected
    proposed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))


class ActionDraft(Base):
    __tablename__ = "action_drafts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    account_id: Mapped[str] = mapped_column(String(64))
    estimate_min: Mapped[Decimal | None] = mapped_column(Money)
    estimate_max: Mapped[Decimal | None] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(16))  # fifo | lifo | prorata
    assumptions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")


class QualityIssue(Base):
    """Intake quality check result (F2): duplicate statements, gaps in
    statement date ranges, balances that do not reconcile, ambiguous date
    formats. Shown in the review queue before analysis runs.

    Not one of the spec's 20 tables: the spec names the checks but no home for
    their results or the officer's acknowledgement."""
    __tablename__ = "quality_issues"
    __table_args__ = (UniqueConstraint("case_id", "check", "issue_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    check: Mapped[str] = mapped_column(String(40))
    issue_key: Mapped[str] = mapped_column(String(200))
    file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN | ACKNOWLEDGED
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40))


# --- audit ---------------------------------------------------------------------

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("hash"),)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    ts: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(48))
    # Canonical JSON of the payload. Kept so payload_hash can be recomputed;
    # case_id is copied out of it only to make scoped reads cheap, and verify
    # checks the copy against the payload.
    payload: Mapped[str] = mapped_column(Text)
    case_id: Mapped[str | None] = mapped_column(String(32), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
