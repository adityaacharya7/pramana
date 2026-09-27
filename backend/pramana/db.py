from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat(timespec="microseconds")


_ENGINES: dict[tuple[str, bool], Engine] = {}


def make_engine(db_url: str, serverless: bool = False) -> Engine:
    key = (db_url, serverless)
    if key in _ENGINES:
        return _ENGINES[key]
    kwargs: dict = {}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Hosted Postgres is usually reached through a transaction-mode pooler
        # (Neon/PgBouncer), where server-side prepared statements can land on
        # a different backend connection. Never prepare them.
        kwargs["connect_args"] = {"prepare_threshold": None}
    if db_url.startswith("sqlite"):
        pass
    elif serverless:
        # Each function instance is short-lived and there may be many of them:
        # hold no idle connections (use the provider's pooled URL for pooling).
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_pre_ping"] = True
    engine = create_engine(db_url, **kwargs)
    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _record):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    _ENGINES[key] = engine
    return engine


def dispose_engine(db_url: str) -> None:
    for key in [k for k in _ENGINES if k[0] == db_url]:
        _ENGINES.pop(key).dispose()


def make_sessionmaker(engine: Engine, settings=None) -> sessionmaker[Session]:
    # Settings ride on each session so after-commit hooks (signed checkpoints)
    # know which deployment they belong to.
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False,
                        info={"settings": settings} if settings is not None else {})


class DeploymentMismatch(RuntimeError):
    pass


class NotInitialised(RuntimeError):
    pass


def check_deployment(session: Session, build: str, create: bool = True) -> bool:
    """Record the build on first use; refuse a database made by the other
    build. Returns True if the database was fresh."""
    from .models import Deployment

    row = session.scalar(select(Deployment))
    if row is None:
        if not create:
            raise NotInitialised("The database has no PRAMANA schema yet. Run `python -m pramana.cli init-db` "
                                 "(or `demo-reset` for the demo build) against it first.")
        try:
            session.add(Deployment(id=1, build=build, created_at=utcnow_iso()))
            session.commit()
            return True
        except IntegrityError:
            # Another instance created it at the same moment.
            session.rollback()
            row = session.scalar(select(Deployment))
    if row.build != build:
        raise DeploymentMismatch(
            f"This database belongs to the {row.build!r} build; refusing to open it as {build!r}."
        )
    return False
