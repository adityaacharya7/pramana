"""Runtime settings.

Two builds exist and never share data:

* ``standard`` - the real application. No role switcher; users sign in with
  password + TOTP.
* ``demo``     - the isolated synthetic demo build, seeded from the synthetic
  dataset, with a role switcher.

The database records which build created it, and the app refuses to start
against a database from the other build (see ``db.check_deployment``).

Two environments:

* local / Docker - SQLite and sealed files under ``var/<build>/`` by default.
* serverless (Vercel, detected from ``VERCEL``) - no persistent disk and many
  short-lived instances. PostgreSQL is required (``PRAMANA_DB_URL``, or the
  ``POSTGRES_URL`` / ``DATABASE_URL`` a Vercel Postgres/Neon integration sets),
  evidence is stored in the database, ``PRAMANA_JWT_SECRET`` must be set, and
  the schema and demo data are created once from the CLI, never by a cold start.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDS = ("standard", "demo")
STORES = ("file", "db")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    build: str
    data_dir: Path
    db_url: str
    evidence_dir: Path
    evidence_store: str  # file | db
    jwt_secret: str
    token_ttl_minutes: int
    max_upload_bytes: int
    dataset_dir: Path
    cors_origins: tuple[str, ...]
    serverless: bool
    manage_schema: bool  # create tables on start-up
    auto_seed: bool  # seed an empty demo database on start-up

    @property
    def is_demo(self) -> bool:
        return self.build == "demo"

    @property
    def is_sqlite(self) -> bool:
        return self.db_url.startswith("sqlite")


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def normalise_db_url(url: str) -> str:
    """Hosted Postgres URLs come as postgres:// or postgresql://; SQLAlchemy
    needs the driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _jwt_secret(data_dir: Path, serverless: bool) -> str:
    env = os.environ.get("PRAMANA_JWT_SECRET")
    if env:
        if len(env) < 32:
            raise ConfigError("PRAMANA_JWT_SECRET must be at least 32 characters.")
        return env
    if serverless:
        # A generated secret would differ per instance and vanish on the next
        # cold start, silently signing everyone out; refuse instead.
        raise ConfigError("Set PRAMANA_JWT_SECRET (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`).")
    # Generated once per data directory, so demo and standard tokens are never
    # interchangeable and restarts keep sessions valid.
    path = data_dir / "jwt_secret"
    if path.exists():
        return path.read_text(encoding="ascii").strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    path.write_text(secret, encoding="ascii")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return secret


def load_settings(build: str | None = None, data_root: Path | None = None) -> Settings:
    build = build or os.environ.get("PRAMANA_BUILD", "standard")
    if build not in BUILDS:
        raise ConfigError(f"PRAMANA_BUILD must be one of {BUILDS}, got {build!r}")
    serverless = _flag("PRAMANA_SERVERLESS", bool(os.environ.get("VERCEL")))
    default_root = Path("/tmp/pramana") if serverless else REPO_ROOT / "var"
    root = Path(data_root or os.environ.get("PRAMANA_DATA_DIR") or default_root)
    data_dir = root / build

    env_url = os.environ.get("PRAMANA_DB_URL") or (
        (os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")) if serverless else None)
    db_file = "pramana_demo.db" if build == "demo" else "pramana.db"
    db_url = normalise_db_url(env_url) if env_url else f"sqlite:///{(data_dir / db_file).as_posix()}"
    if serverless and db_url.startswith("sqlite"):
        raise ConfigError("Serverless deployments need PostgreSQL: set PRAMANA_DB_URL or connect Vercel Postgres/Neon "
                          "(POSTGRES_URL). A SQLite file would vanish with the instance.")

    store = os.environ.get("PRAMANA_EVIDENCE_STORE") or ("file" if db_url.startswith("sqlite") else "db")
    if store not in STORES:
        raise ConfigError(f"PRAMANA_EVIDENCE_STORE must be one of {STORES}")
    if serverless and store == "file":
        raise ConfigError("Serverless deployments must store evidence in the database (PRAMANA_EVIDENCE_STORE=db).")

    origins = os.environ.get("PRAMANA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    # Vercel functions accept request bodies up to 4.5 MB.
    default_upload_mb = "4" if serverless else "25"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        build=build,
        data_dir=data_dir,
        db_url=db_url,
        evidence_dir=data_dir / "evidence",
        evidence_store=store,
        jwt_secret=_jwt_secret(data_dir, serverless),
        token_ttl_minutes=int(os.environ.get("PRAMANA_TOKEN_TTL_MINUTES", "30")),
        max_upload_bytes=int(float(os.environ.get("PRAMANA_MAX_UPLOAD_MB", default_upload_mb)) * 1024 * 1024),
        dataset_dir=Path(os.environ.get("PRAMANA_DATASET_DIR") or REPO_ROOT / "dataset" / "tri_city_v1"),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        serverless=serverless,
        manage_schema=_flag("PRAMANA_MANAGE_SCHEMA", not serverless),
        auto_seed=_flag("PRAMANA_AUTO_SEED", not serverless),
    )
