from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ledger, storage
from ..config import Settings
from ..db import utcnow_iso
from ..deps import current_user, get_db, get_settings
from ..models import EvidenceFile, User, new_id
from ..permissions import require_case
from ..schemas import EvidenceOut, VerifyOut

router = APIRouter(tags=["evidence"])

MEDIA = {"CSV": "text/csv; charset=utf-8", "TXT": "text/plain; charset=utf-8", "PDF": "application/pdf"}
BLOCKED = "Integrity mismatch: this file has changed since it was sealed and is blocked from use."


def evidence_out(ev: EvidenceFile, uploader: User | None) -> EvidenceOut:
    return EvidenceOut(
        id=ev.id, case_id=ev.case_id, filename=ev.filename, type=ev.type, kind=ev.kind, sha256=ev.sha256,
        size_bytes=ev.size_bytes, uploaded_by=uploader.username if uploader else ev.uploaded_by,
        uploaded_by_name=uploader.name if uploader else "", uploaded_at=ev.uploaded_at,
        integrity_status=ev.integrity_status, last_verified_at=ev.last_verified_at,
        source_group_id=ev.source_group_id,
        duplicate_of=ev.source_group_id if ev.source_group_id != ev.id else None,
    )


def seal(db: Session, settings: Settings, *, case_id: str, stream, filename: str, kind: str,
         uploaded_by: User, actor: str, extra: dict | None = None) -> EvidenceFile:
    """Store a file, record its manifest row and ledger entry together.
    Shared by the upload endpoint and the demo seed."""
    file_id = new_id()
    name = storage.clean_filename(filename)
    rel, sha, size, ftype = storage.store(settings, case_id, file_id, stream, name)
    # Byte-identical copies within a case form one source group, so a second
    # copy is never counted as independent corroboration.
    first = db.scalar(select(EvidenceFile).where(EvidenceFile.case_id == case_id, EvidenceFile.sha256 == sha)
                      .order_by(EvidenceFile.uploaded_at).limit(1))
    now = utcnow_iso()
    ev = EvidenceFile(id=file_id, case_id=case_id, filename=name, type=ftype, kind=kind, sha256=sha,
                      size_bytes=size, storage_path=rel, uploaded_by=uploaded_by.id, uploaded_at=now,
                      integrity_status="OK", last_verified_at=now,
                      source_group_id=first.source_group_id if first else file_id)
    try:
        with ledger.transaction(db):
            db.add(ev)
            ledger.append(db, actor=actor, action="EVIDENCE_UPLOADED", payload={
                "case_id": case_id, "evidence_id": file_id, "filename": name, "sha256": sha,
                "size_bytes": size, "type": ftype, "kind": kind,
                "duplicate_of": first.id if first else None, **(extra or {}),
            })
    except Exception:
        storage.discard(settings, rel)
        raise
    return ev


@router.post("/cases/{case_id}/evidence", response_model=EvidenceOut, status_code=201)
def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    kind: str = Form("unclassified"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    case = require_case(db, user, case_id, "evidence.upload")
    if kind not in storage.KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown evidence kind {kind!r}.")
    try:
        ev = seal(db, settings, case_id=case.id, stream=file.file, filename=file.filename or "", kind=kind,
                  uploaded_by=user, actor=user.username)
    except storage.UploadRejected as e:
        ledger.record(db, actor=user.username, action="EVIDENCE_UPLOAD_REJECTED",
                      payload={"case_id": case.id, "filename": storage.clean_filename(file.filename or ""),
                               "reason": str(e)})
        raise HTTPException(status_code=413 if "limit" in str(e) else 422, detail=str(e))
    return evidence_out(ev, user)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = require_case(db, user, case_id, "evidence.read")
    rows = db.execute(
        select(EvidenceFile, User).outerjoin(User, User.id == EvidenceFile.uploaded_by)
        .where(EvidenceFile.case_id == case.id).order_by(EvidenceFile.uploaded_at)
    ).all()
    return [evidence_out(ev, u) for ev, u in rows]


def _load(db: Session, user: User, evidence_id: str, action: str) -> EvidenceFile:
    ev = db.get(EvidenceFile, evidence_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Evidence file not found.")
    require_case(db, user, ev.case_id, action)
    return ev


def _mark(db: Session, ev: EvidenceFile, status: str, actual: str | None, actor: str) -> None:
    changed = ev.integrity_status != status
    with ledger.transaction(db):
        ev.integrity_status = status
        ev.last_verified_at = utcnow_iso()
        if status == "OK":
            action = "EVIDENCE_INTEGRITY_RESTORED" if changed else "EVIDENCE_VERIFIED"
        else:
            action = "EVIDENCE_INTEGRITY_MISMATCH"
        ledger.append(db, actor=actor, action=action, payload={
            "case_id": ev.case_id, "evidence_id": ev.id, "filename": ev.filename,
            "expected_sha256": ev.sha256, "actual_sha256": actual, "status": status,
        })


@router.get("/evidence/{evidence_id}/verify", response_model=VerifyOut)
def verify_evidence(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                    settings: Settings = Depends(get_settings)):
    ev = _load(db, user, evidence_id, "evidence.verify")
    actual = storage.rehash(settings, ev.storage_path)
    status = "MISSING" if actual is None else ("OK" if actual == ev.sha256 else "MISMATCH")
    _mark(db, ev, status, actual, user.username)
    return VerifyOut(evidence_id=ev.id, filename=ev.filename, expected_sha256=ev.sha256, actual_sha256=actual,
                     status=status, verified_at=ev.last_verified_at or "")


@router.get("/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db),
                     settings: Settings = Depends(get_settings)):
    """The file itself, re-hashed on every load. A mismatch blocks it."""
    ev = _load(db, user, evidence_id, "evidence.read")
    try:
        data = storage.read_verified(settings, ev.storage_path, ev.sha256)
    except storage.IntegrityMismatch as e:
        _mark(db, ev, "MISSING" if e.actual is None else "MISMATCH", e.actual, user.username)
        raise HTTPException(status_code=409, detail=BLOCKED)
    if ev.integrity_status != "OK":
        _mark(db, ev, "OK", ev.sha256, user.username)
    return Response(content=data, media_type=MEDIA[ev.type], headers={
        "X-Evidence-SHA256": ev.sha256,
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(ev.filename)}",
    })
