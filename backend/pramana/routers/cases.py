from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import current_user, get_db
from ..models import Case, CaseMember, EvidenceFile, User
from ..permissions import require_case, visible_case_ids
from ..schemas import CaseDetailOut, CaseOut, MemberOut

router = APIRouter(tags=["cases"])


def _case_out(c: Case, access: str, evidence_count: int) -> dict:
    return dict(id=c.id, fir_no=c.fir_no, unit=c.unit, city=c.city, status=c.status, title=c.title,
                station=c.station, registered_on=c.registered_on, complainant=c.complainant,
                my_access=access, evidence_count=evidence_count)


@router.get("/cases", response_model=list[CaseOut])
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = visible_case_ids(db, user)
    if not ids:
        return []
    cases = db.scalars(select(Case).where(Case.id.in_(ids)).order_by(Case.id)).all()
    counts = dict(db.execute(
        select(EvidenceFile.case_id, func.count()).where(EvidenceFile.case_id.in_(ids)).group_by(EvidenceFile.case_id)
    ).all())
    access = dict(db.execute(select(CaseMember.case_id, CaseMember.access).where(CaseMember.user_id == user.id)).all())
    return [CaseOut(**_case_out(c, access.get(c.id, "unit"), counts.get(c.id, 0))) for c in cases]


@router.get("/cases/{case_id}", response_model=CaseDetailOut)
def get_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = require_case(db, user, case_id, "case.view")
    members = db.execute(
        select(User, CaseMember.access).join(CaseMember, CaseMember.user_id == User.id)
        .where(CaseMember.case_id == case.id).order_by(CaseMember.access.desc(), User.name)
    ).all()
    mine = next((a for u, a in members if u.id == user.id), "unit")
    count = db.scalar(select(func.count()).select_from(EvidenceFile).where(EvidenceFile.case_id == case.id)) or 0
    return CaseDetailOut(
        **_case_out(case, mine, count),
        members=[MemberOut(username=u.username, name=u.name, role=u.role, access=a) for u, a in members],
    )


class CreateCaseIn(BaseModel):
    fir_no: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=256)
    complainant: str = Field(min_length=1, max_length=128)
    city: str | None = None
    unit: str = Field(min_length=1, max_length=32)
    station: str | None = None


@router.post("/cases", response_model=CaseDetailOut, status_code=201)
def create_case(body: CreateCaseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .. import ledger
    from ..db import utcnow_iso
    now = utcnow_iso()
    count = db.scalar(select(func.count()).select_from(Case)) or 0
    case_id = f"C-{100 + count + 1}"
    case = Case(
        id=case_id,
        fir_no=body.fir_no,
        unit=body.unit,
        city=body.city,
        status="OPEN",
        title=body.title,
        station=body.station or f"{body.city or body.unit} Cyber Crime PS",
        registered_on=now.split("T")[0],
        complainant=body.complainant,
        created_at=now,
    )
    with ledger.transaction(db):
        db.add(case)
        db.flush()
        db.add(CaseMember(case_id=case.id, user_id=user.id, access="owner", granted_at=now, granted_by=user.username))
        ledger.append(db, actor=user.username, action="CASE_CREATED", payload={
            "case_id": case.id, "fir_no": case.fir_no, "unit": case.unit,
            "title": case.title, "complainant": case.complainant,
        })
    return CaseDetailOut(
        **_case_out(case, "owner", 0),
        members=[MemberOut(username=user.username, name=user.name, role=user.role, access="owner")],
    )
