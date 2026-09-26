from __future__ import annotations

from typing import Iterator

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    settings: Settings = request.app.state.settings
    unauthorised = HTTPException(status_code=401, detail="Sign in required.",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorised
    try:
        claims = decode_token(creds.credentials, settings)
    except jwt.PyJWTError:
        raise unauthorised
    if claims.get("build") != settings.build:
        raise unauthorised
    user = db.get(User, claims["sub"])
    # A role or unit change invalidates existing sessions: the token must
    # still describe the user as they are now.
    if user is None or not user.is_active or claims.get("role") != user.role or claims.get("unit") != user.unit:
        raise unauthorised
    return user
