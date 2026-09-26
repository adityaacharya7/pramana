from __future__ import annotations

import dataclasses
import os
import time

os.environ.setdefault("PRAMANA_BCRYPT_ROUNDS", "4")

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from pramana import ledger  # noqa: E402
from pramana.config import load_settings  # noqa: E402
from pramana.db import utcnow_iso  # noqa: E402
from pramana.main import create_app  # noqa: E402
from pramana.models import Case, CaseMember, LedgerEntry, User  # noqa: E402
from pramana.security import hash_password, new_totp_secret  # noqa: E402

PASSWORD = "correct horse battery staple"

# Set PRAMANA_TEST_PG_URL (a PostgreSQL server URL, e.g. from pgserver) to run
# the whole suite against PostgreSQL with evidence stored in the database -
# the configuration a Vercel deployment uses. Default: SQLite + files.
PG_URL = os.environ.get("PRAMANA_TEST_PG_URL")


def make_settings(build: str, root):
    os.environ.pop("PRAMANA_DB_URL", None)
    settings = load_settings(build, data_root=root)
    if not PG_URL:
        return settings
    import uuid
    from sqlalchemy import create_engine, text
    from pramana.config import normalise_db_url
    name = f"pramana_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(normalise_db_url(PG_URL), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    base = normalise_db_url(PG_URL).rsplit("/", 1)[0]
    return dataclasses.replace(settings, db_url=f"{base}/{name}", evidence_store="db")


def tamper(app, evidence_id: str, new_bytes: bytes | None) -> None:
    """Change (or, with None, delete) a sealed file behind the app's back."""
    from pramana.models import EvidenceBlob, EvidenceFile
    settings = app.state.settings
    with app.state.sessionmaker() as s:
        ev = s.get(EvidenceFile, evidence_id)
        if settings.evidence_store == "db":
            blob = s.get(EvidenceBlob, ev.storage_path)
            if new_bytes is None:
                s.delete(blob)
            else:
                blob.data = new_bytes
            s.commit()
            return
        path = settings.evidence_dir / ev.storage_path
    os.chmod(path, 0o644)
    if new_bytes is None:
        path.unlink()
    else:
        path.write_bytes(new_bytes)


@pytest.fixture
def app(tmp_path):
    return create_app(make_settings("standard", tmp_path))


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    session = app.state.sessionmaker()
    yield session
    session.close()


def make_user(db, username, role, unit):
    with ledger.transaction(db):
        user = User(username=username, name=username.replace(".", " ").title(), role=role, unit=unit,
                    password_hash=hash_password(PASSWORD), totp_secret=new_totp_secret(), created_at=utcnow_iso())
        db.add(user)
    return user


def make_case(db, case_id, unit, members):
    with ledger.transaction(db):
        db.add(Case(id=case_id, fir_no=f"{case_id}/2026", unit=unit, city=None, title=f"Case {case_id}",
                    status="OPEN", created_at=utcnow_iso()))
        db.flush()
        for username, access in members.items():
            user = db.scalar(select(User).where(User.username == username))
            db.add(CaseMember(case_id=case_id, user_id=user.id, access=access, granted_at=utcnow_iso()))


@pytest.fixture
def world(db):
    """Two units. C-1 belongs to Mumbai, C-2 to Delhi."""
    for username, role, unit in [
        ("io.mum", "IO", "MUM"), ("io.del", "IO", "DEL"), ("analyst.mum", "ANALYST", "MUM"),
        ("sup.mum", "SUPERVISOR", "MUM"), ("sup.del", "SUPERVISOR", "DEL"),
        ("auditor", "AUDITOR", "VIG"), ("admin", "ADMIN", "IT"),
    ]:
        make_user(db, username, role, unit)
    make_case(db, "C-1", "MUM", {"io.mum": "owner", "analyst.mum": "member"})
    make_case(db, "C-2", "DEL", {"io.del": "owner"})
    return db


def next_code(db, username: str) -> str:
    """A valid one-time code the server has not seen yet for this user."""
    user = db.scalar(select(User).where(User.username == username))
    db.refresh(user)
    totp = pyotp.TOTP(user.totp_secret)
    now_step = int(time.time() // 30)
    for step in (now_step - 1, now_step, now_step + 1):
        if user.totp_last_step is None or step > user.totp_last_step:
            return totp.generate_otp(step)
    raise RuntimeError("no unused TOTP step left in the window")


def login(client, db, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": PASSWORD, "totp": next_code(db, username)})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def entries(db, action: str | None = None):
    db.expire_all()
    q = select(LedgerEntry).order_by(LedgerEntry.seq)
    if action:
        q = q.where(LedgerEntry.action == action)
    return db.scalars(q).all()
