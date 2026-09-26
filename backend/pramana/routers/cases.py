from __future__ import annotations

from fastapi import APIRouter, Depends
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
