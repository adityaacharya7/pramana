from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    totp: str = Field(min_length=6, max_length=8)


class UserOut(BaseModel):
    id: str
    username: str
    name: str
    role: str
    role_label: str
    unit: str


class SessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserOut


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]
    build: str


class MemberOut(BaseModel):
    username: str
    name: str
    role: str
    access: str


class CaseOut(BaseModel):
    id: str
    fir_no: str
    unit: str
    city: str | None
    status: str
    title: str
    station: str | None
    registered_on: str | None
    complainant: str | None
    my_access: str  # owner | member | unit
    evidence_count: int


class CaseDetailOut(CaseOut):
    members: list[MemberOut]


class EvidenceOut(BaseModel):
    id: str
    case_id: str
    filename: str
    type: str
    kind: str
    sha256: str
    size_bytes: int
    uploaded_by: str
    uploaded_by_name: str
    uploaded_at: str
    integrity_status: str
    last_verified_at: str | None
    source_group_id: str
    duplicate_of: str | None = None


class VerifyOut(BaseModel):
    evidence_id: str
    filename: str
    expected_sha256: str
    actual_sha256: str | None
    status: str
    verified_at: str


class LedgerEntryOut(BaseModel):
    seq: int
    ts: str
    actor: str
    action: str
    case_id: str | None
    payload: dict[str, Any]
    hash: str
    prev_hash: str


class DemoSessionRequest(BaseModel):
    username: str
