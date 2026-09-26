"""Role switcher. Mounted only in the isolated synthetic demo build, which
runs on its own database; the standard build has no route to it at all."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ledger
from ..config import Settings
from ..deps import get_db, get_settings
from ..models import User
from ..schemas import DemoSessionRequest, SessionOut, UserOut
from .auth import session_out, user_out

router = APIRouter(prefix="/demo", tags=["demo build only"])


@router.get("/users", response_model=list[UserOut])
def demo_users(db: Session = Depends(get_db)):
    order = {"IO": 0, "ANALYST": 1, "SUPERVISOR": 2, "AUDITOR": 3, "ADMIN": 4}
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    return [user_out(u) for u in sorted(users, key=lambda u: (order.get(u.role, 9), u.unit, u.username))]


@router.post("/session", response_model=SessionOut)
def demo_session(body: DemoSessionRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = db.scalar(select(User).where(User.username == body.username, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=404, detail="No such demo user.")
    ledger.record(db, actor=user.username, action="DEMO_SESSION_STARTED",
                  payload={"role": user.role, "unit": user.unit, "method": "demo role switcher"})
    return session_out(user, settings)
