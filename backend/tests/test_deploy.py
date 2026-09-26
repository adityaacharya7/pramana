"""Serverless (Vercel) configuration and the Vercel entry point."""
import importlib.util
import threading

import pytest
from fastapi.testclient import TestClient

from pramana import ledger
from pramana.config import REPO_ROOT, ConfigError, load_settings, normalise_db_url
from pramana.db import NotInitialised, check_deployment, make_engine, make_sessionmaker
from pramana.main import create_app

from .conftest import PG_URL, make_settings

SECRET = "x" * 48


def test_hosted_postgres_urls_get_a_driver():
    assert normalise_db_url("postgres://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalise_db_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalise_db_url("sqlite:///x.db") == "sqlite:///x.db"


def test_serverless_refuses_unsafe_configuration(monkeypatch, tmp_path):
    for k in ("PRAMANA_DB_URL", "POSTGRES_URL", "DATABASE_URL", "PRAMANA_JWT_SECRET", "PRAMANA_EVIDENCE_STORE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ConfigError, match="PostgreSQL"):
        load_settings("demo", data_root=tmp_path)  # no database configured
    monkeypatch.setenv("POSTGRES_URL", "postgres://u:p@db.example/pramana")
    with pytest.raises(ConfigError, match="PRAMANA_JWT_SECRET"):
        load_settings("demo", data_root=tmp_path)  # no signing secret
    monkeypatch.setenv("PRAMANA_JWT_SECRET", "short")
    with pytest.raises(ConfigError, match="32"):
        load_settings("demo", data_root=tmp_path)
    monkeypatch.setenv("PRAMANA_JWT_SECRET", SECRET)
    monkeypatch.setenv("PRAMANA_EVIDENCE_STORE", "file")
    with pytest.raises(ConfigError, match="database"):
        load_settings("demo", data_root=tmp_path)  # evidence on an ephemeral disk
    monkeypatch.delenv("PRAMANA_EVIDENCE_STORE")

    s = load_settings("demo", data_root=tmp_path)
    assert s.serverless and s.db_url.startswith("postgresql+psycopg://") and s.evidence_store == "db"
    assert not s.manage_schema and not s.auto_seed
    assert s.max_upload_bytes == 4 * 1024 * 1024  # Vercel's request body limit


def test_cold_start_never_creates_schema_or_seeds(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    from pramana.db import Base
    Base.metadata.create_all(engine)
    with make_sessionmaker(engine)() as db:
        with pytest.raises(NotInitialised, match="init-db"):
            check_deployment(db, "demo", create=False)


def test_vercel_entry_point_serves_the_api_under_api(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAMANA_BUILD", "demo")
    monkeypatch.setenv("PRAMANA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAMANA_DB_URL", raising=False)
    spec = importlib.util.spec_from_file_location("vercel_index", REPO_ROOT / "api" / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    client = TestClient(mod.app)
    assert client.get("/api/health").json()["build"] == "demo"
    assert len(client.get("/api/demo/users").json()) == 9
    assert client.get("/health").status_code == 404  # only /api is the function's


@pytest.mark.skipif(not PG_URL, reason="needs PRAMANA_TEST_PG_URL (see tests/run_postgres.py)")
def test_parallel_writers_keep_one_unbroken_chain(tmp_path):
    """Serverless instances append concurrently; the advisory lock must keep
    sequence numbers gap-free and the chain valid. Separate engines stand in
    for separate instances (no shared in-process lock is relied on)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker as sm
    from sqlalchemy.pool import NullPool
    settings = make_settings("standard", tmp_path)
    create_app(settings)
    errors = []

    def writer(n):
        # A private engine and a private lock object: only PostgreSQL serialises.
        engine = create_engine(settings.db_url, poolclass=NullPool)
        s = sm(bind=engine)()
        try:
            for i in range(10):
                with s.begin():
                    s.execute(text("SELECT pg_advisory_xact_lock(:k)"),
                              {"k": ledger.LEDGER_LOCK_KEY})
                    lock = ledger._LOCK
                    lock.acquire()  # satisfy append()'s in-process guard in this thread
                    try:
                        ledger.append(s, actor=f"w{n}", action="TEST", payload={"i": i})
                    finally:
                        lock.release()
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            s.close()
            engine.dispose()

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    with make_sessionmaker(make_engine(settings.db_url))() as db:
        report = ledger.verify(db)
    assert report["ok"] and report["entries"] >= 40
