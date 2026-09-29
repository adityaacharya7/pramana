"""Role x action permission matrix, enforced server-side.

Two layers (spec, "Users and roles"): the role decides what a user can do;
case membership decides which cases they can do it on.

Scopes
  MEMBER  the user is an owner or member of the case ("own" / "authorised" cases)
  UNIT    the case belongs to the user's unit, or the user is a member
  ANY     not tied to a case

Only Week 1 actions are listed; each later endpoint adds its row here from
the spec's matrix rather than checking roles inline.
"""
from __future__ import annotations

from enum import Enum

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import ledger
from .models import Case, CaseMember, User


class Role(str, Enum):
    IO = "IO"
    ANALYST = "ANALYST"
    SUPERVISOR = "SUPERVISOR"
    AUDITOR = "AUDITOR"
    ADMIN = "ADMIN"
    TRAINEE = "TRAINEE"


ROLE_LABELS = {
    Role.IO: "Investigating Officer", Role.ANALYST: "Intelligence Analyst",
    Role.SUPERVISOR: "Supervisory Officer", Role.AUDITOR: "Auditor", Role.ADMIN: "Admin",
    Role.TRAINEE: "Trainee",
}

MEMBER, UNIT, ANY = "member", "unit", "any"
EVERYONE = {r: ANY for r in Role}

MATRIX: dict[str, dict[Role, str]] = {
    "case.view": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    # Registering a complaint: always in the officer's own unit (enforced in the router).
    "case.create": {Role.IO: ANY, Role.SUPERVISOR: ANY},
    "evidence.upload": {Role.IO: MEMBER},
    "evidence.read": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "evidence.verify": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "ledger.verify": EVERYONE,
    # Week 2: extraction, review, identity, graph (spec permission matrix and
    # endpoint table: extraction and review are the IO's, with supervisor
    # oversight; analysts read the graph but do not edit evidence).
    "extraction.run": {Role.IO: MEMBER},
    "review.read": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},
    "extraction.decide": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},
    "identity.decide": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},
    "quality.decide": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},
    "graph.read": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    # Weeks 3-5 (spec permission matrix): IO own cases, Analyst authorised
    # cases, Supervisor unit cases. A lead spanning cases needs all of them.
    "analysis.run": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "lead.read": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "lead.challenge": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "lead.transition": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},  # IO proposes, supervisor approves
    "scenario.decide": {Role.IO: MEMBER, Role.SUPERVISOR: UNIT},  # IO proposes, supervisor applies
    "draft.create": {Role.IO: MEMBER},
    "draft.approve": {Role.SUPERVISOR: UNIT},
    "lead.export": {Role.IO: MEMBER, Role.ANALYST: MEMBER, Role.SUPERVISOR: UNIT},
    "access.request": {Role.IO: ANY, Role.ANALYST: ANY, Role.SUPERVISOR: ANY},
    "access.decide": {Role.SUPERVISOR: ANY},  # further limited to the owning unit's supervisor
    "bundle.verify": EVERYONE,
    # Auditors read the whole trail; supervisors read entries for cases in
    # their scope (filtered in the query).
    "ledger.read": {Role.AUDITOR: ANY, Role.SUPERVISOR: UNIT},
}


def allowed_actions(role: str) -> list[str]:
    r = Role(role)
    return sorted(a for a, rules in MATRIX.items() if r in rules)


def _membership(db: Session, user: User, case_id: str) -> CaseMember | None:
    return db.get(CaseMember, (case_id, user.id))


def in_scope(db: Session, user: User, case: Case, scope: str) -> bool:
    if scope == ANY:
        return True
    if _membership(db, user, case.id):
        return True
    return scope == UNIT and case.unit == user.unit


def _refuse(db: Session, user: User, action: str, case_id: str | None, reason: str) -> HTTPException:
    ledger.record(db, actor=user.username, action="ACCESS_REFUSED",
                  payload={"case_id": case_id, "attempted": action, "role": user.role, "unit": user.unit,
                           "reason": reason})
    return HTTPException(status_code=403, detail="You do not have access to this. The attempt has been logged.")


def require_action(db: Session, user: User, action: str) -> str:
    """For actions not tied to one case. Returns the scope granted."""
    scope = MATRIX[action].get(Role(user.role))
    if scope is None:
        raise _refuse(db, user, action, None, "role not permitted")
    return scope


def require_case(db: Session, user: User, case_id: str, action: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    scope = MATRIX[action].get(Role(user.role))
    if scope is None:
        raise _refuse(db, user, action, case_id, "role not permitted")
    if not in_scope(db, user, case, scope):
        raise _refuse(db, user, action, case_id, "case outside the user's scope")
    return case


def require_cases(db: Session, user: User, case_ids: list[str], action: str) -> list[Case]:
    if not case_ids:
        raise HTTPException(status_code=422, detail="Choose at least one case.")
    return [require_case(db, user, c, action) for c in sorted(set(case_ids))]


def visible_case_ids(db: Session, user: User, action: str = "case.view") -> list[str]:
    scope = MATRIX[action].get(Role(user.role))
    if scope is None:
        return []
    member_ids = select(CaseMember.case_id).where(CaseMember.user_id == user.id)
    q = select(Case.id)
    if scope == ANY:
        pass
    elif scope == UNIT:
        q = q.where(or_(Case.unit == user.unit, Case.id.in_(member_ids)))
    else:
        q = q.where(Case.id.in_(member_ids))
    return list(db.scalars(q.order_by(Case.id)))
