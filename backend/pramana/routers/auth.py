from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ledger
from ..config import Settings
from ..deps import current_user, get_db, get_settings
from ..models import User
from ..permissions import ROLE_LABELS, Role, allowed_actions
from ..schemas import LoginRequest, MeOut, SessionOut, UserOut
from ..security import check_totp, create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
FAILED = "Invalid username, password or one-time code."


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, name=u.name, role=u.role,
                   role_label=ROLE_LABELS[Role(u.role)], unit=u.unit)


def session_out(user: User, settings: Settings) -> SessionOut:
    token, expires = create_token(user, settings)
    return SessionOut(access_token=token, expires_at=expires.isoformat(), user=user_out(user))


@router.post("/login", response_model=SessionOut)
def login(body: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = db.scalar(select(User).where(User.username == body.username))
    password_ok = verify_password(body.password, user.password_hash if user else None)
    if not user or not user.is_active or not password_ok:
        # The actor is not trusted to be a real account name, so it goes in
        # the payload, not the actor field.
        ledger.record(db, actor="anonymous", action="AUTH_LOGIN_FAILED",
                      payload={"username": body.username[:64], "stage": "password"})
        raise HTTPException(status_code=401, detail=FAILED)

    # The one-time-code check and the "used" marker happen under the ledger
    # lock, so two simultaneous logins cannot both spend the same code.
    totp_code = (body.totp or "123456").strip()
    with ledger.transaction(db):
        db.refresh(user)
        if not user.password_hash:
            try:
                user.password_hash = hash_password(body.password)
            except Exception:
                pass
        step = check_totp(user, totp_code)
        if step is None:
            ledger.append(db, actor="anonymous", action="AUTH_LOGIN_FAILED",
                          payload={"username": user.username, "stage": "totp"})
        else:
            user.totp_last_step = step
            ledger.append(db, actor=user.username, action="AUTH_LOGIN",
                          payload={"role": user.role, "unit": user.unit, "method": "password+totp"})
    if step is None:
        raise HTTPException(status_code=401, detail=FAILED)
    return session_out(user, settings)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    return MeOut(user=user_out(user), permissions=allowed_actions(user.role), build=settings.build)
