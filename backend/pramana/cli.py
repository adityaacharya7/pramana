"""Operator commands.

    python -m pramana.cli serve [--demo] [--port 8000]
    python -m pramana.cli demo-reset [--hold-back-complaints] [--yes]
    python -m pramana.cli init-db [--demo]
    python -m pramana.cli verify-bundle bundle.json [--public-key KEY]
    python -m pramana.cli create-user --username u --name "Full Name" --role IO --unit MUM-CYB
    python -m pramana.cli create-case --id C-900 --fir-no 0001/2026 --unit MUM-CYB --title "..."
    python -m pramana.cli add-member --case C-900 --username u [--access owner]
    python -m pramana.cli verify-ledger [--demo]

User and case administration belongs to the Admin role (P1); until that UI
exists, these commands are how a standard build gets its first accounts.

Against a hosted database (e.g. the Vercel deployment's Postgres), set
PRAMANA_DB_URL to its URL and run the same commands from your machine.
"""
from __future__ import annotations

import argparse
import getpass
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import select

from . import ledger
from .config import load_settings
from .db import utcnow_iso
from .main import create_app
from .models import Case, CaseMember, User
from .permissions import Role
from .security import hash_password, new_totp_secret, totp_uri

ADMIN_ACTOR = "cli:operator"


def _db(build: str):
    app = create_app(load_settings(build))
    return app, app.state.sessionmaker()


def cmd_serve(args):
    import uvicorn
    app = create_app(load_settings("demo" if args.demo else "standard"))
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_demo_reset(args):
    from sqlalchemy import inspect, select

    from .db import Base, check_deployment, dispose_engine, make_engine, make_sessionmaker
    from .models import Deployment
    from .seed import seed_demo

    settings = load_settings("demo")
    if settings.is_sqlite:
        # Only the demo build's own directory is ever removed.
        if settings.data_dir.name != "demo":
            sys.exit("refusing: unexpected demo data directory")
        shutil.rmtree(settings.data_dir, ignore_errors=True)
        # Checkpoints of the old chain would never match the new one.
        shutil.rmtree(settings.checkpoint_dir, ignore_errors=True)
        if (settings.data_dir / "pramana_demo.db").exists():
            sys.exit("Could not remove the demo database. Stop the demo server first, then retry.")
        settings = load_settings("demo")
    else:
        # A hosted database: wipe it only if it is empty or already a demo
        # database, and only when asked explicitly.
        engine = make_engine(settings.db_url)
        if inspect(engine).has_table("deployment"):
            with make_sessionmaker(engine)() as db:
                row = db.scalar(select(Deployment))
            if row is not None and row.build != "demo":
                sys.exit(f"refusing: this database belongs to the {row.build!r} build.")
        if not args.yes:
            sys.exit(f"This drops every PRAMANA table in {engine.url.render_as_string(hide_password=True)} "
                     "and reseeds it with synthetic data. Re-run with --yes to proceed.")
        summary = _seed_via_local_copy(settings, not args.hold_back_complaints)
        print(json.dumps(summary, indent=2))
        return
    engine = make_engine(settings.db_url)
    Base.metadata.create_all(engine)
    with make_sessionmaker(engine, settings)() as db:
        check_deployment(db, "demo")
        summary = seed_demo(db, settings, preload_all=not args.hold_back_complaints)
    print(json.dumps(summary, indent=2))


def _drop_all(engine) -> None:
    """Drop every PRAMANA table. On PostgreSQL, CASCADE clears constraints left
    by older schema versions too."""
    from sqlalchemy import text
    from .db import Base
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for name in Base.metadata.tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    else:
        Base.metadata.drop_all(engine)


def _seed_via_local_copy(settings, preload_all: bool, batch: int = 500) -> dict:
    """Seeding makes thousands of small, dependent queries: fine next to the
    database, hours over a long network path. So build the demo data in a
    temporary local database (evidence stored in the database, as the hosted
    build does), then copy every table across in batches. Rows are copied
    verbatim, so the audit-log hash chain verifies unchanged."""
    import dataclasses
    import tempfile
    import time

    from .db import Base, check_deployment, dispose_engine, make_engine, make_sessionmaker
    from .seed import seed_demo
    from . import ledger as ledger_mod

    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="pramana-seed-"))
    local = dataclasses.replace(settings, db_url=f"sqlite:///{(tmp / 'seed.db').as_posix()}", evidence_store="db")
    shutil.rmtree(settings.checkpoint_dir, ignore_errors=True)
    src_engine = make_engine(local.db_url)
    Base.metadata.create_all(src_engine)
    with make_sessionmaker(src_engine, local)() as db:
        check_deployment(db, "demo")
        summary = seed_demo(db, local, preload_all=preload_all)
    print(f"built locally in {time.time() - t0:.0f}s; copying to the hosted database…", file=sys.stderr)

    dst_engine = make_engine(settings.db_url)
    _drop_all(dst_engine)
    dispose_engine(settings.db_url)
    dst_engine = make_engine(settings.db_url)
    Base.metadata.create_all(dst_engine)
    copied = {}
    with src_engine.connect() as src, dst_engine.begin() as dst:
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in src.execute(table.select())]
            for i in range(0, len(rows), batch):
                dst.execute(table.insert(), rows[i:i + batch])
            copied[table.name] = len(rows)
    dispose_engine(local.db_url)
    shutil.rmtree(tmp, ignore_errors=True)

    with make_sessionmaker(dst_engine)() as db:
        report = ledger_mod.verify(db)
    if not report["ok"]:
        sys.exit(f"copied, but the audit log does not verify: {report['reason']}")
    return {**summary, "rows_copied": sum(copied.values()), "ledger_verified": report["ok"],
            "seconds": round(time.time() - t0)}


def cmd_verify_bundle(args):
    """Re-run a handover bundle with no database: the 'second, clean offline
    environment' check (F15). Optionally pin the checkpoint key you trust."""
    import base64
    from .analysis.bundle import verify_bundle
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    key = None
    if args.public_key:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(args.public_key))
    report = verify_bundle(bundle, trusted_public_key=key)
    for c in report["checks"]:
        print(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print("REPRODUCED" if report["ok"] else "NOT REPRODUCED")
    sys.exit(0 if report["ok"] else 1)


def cmd_checkpoint_key(args):
    """Generate an Ed25519 key pair for signing audit-log checkpoints. Keep
    the private key off the application server where you can (a supervisor's
    token); on Vercel set it as PRAMANA_CHECKPOINT_KEY."""
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print(f"PRAMANA_CHECKPOINT_KEY={base64.b64encode(raw).decode()}")
    print(f"PRAMANA_CHECKPOINT_PUBLIC_KEY={base64.b64encode(pub).decode()}")


def cmd_init_db(args):
    """Create the schema and claim the database for a build. Needed once for a
    hosted database, since serverless instances never create schema."""
    from .db import Base, check_deployment, make_engine, make_sessionmaker
    settings = load_settings("demo" if args.demo else "standard")
    engine = make_engine(settings.db_url)
    Base.metadata.create_all(engine)
    with make_sessionmaker(engine)() as db:
        fresh = check_deployment(db, settings.build)
    print(f"{'Initialised' if fresh else 'Already initialised'}: {settings.build} build at "
          f"{engine.url.render_as_string(hide_password=True)}")


def cmd_create_user(args):
    Role(args.role)
    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Password: ")
    _, db = _db("standard")
    with db, ledger.transaction(db):
        user = User(username=args.username, name=args.name, role=args.role, unit=args.unit,
                    password_hash=hash_password(password), totp_secret=new_totp_secret(), created_at=utcnow_iso())
        db.add(user)
        db.flush()
        ledger.append(db, actor=ADMIN_ACTOR, action="USER_CREATED",
                      payload={"username": user.username, "role": user.role, "unit": user.unit})
    print(f"Created {args.username} ({args.role}, {args.unit}).")
    print("Add this to an authenticator app now; it is not shown again:")
    print(f"  {totp_uri(user)}")


def cmd_create_case(args):
    _, db = _db("standard")
    with db, ledger.transaction(db):
        db.add(Case(id=args.id, fir_no=args.fir_no, unit=args.unit, city=args.city, title=args.title,
                    status="OPEN", created_at=utcnow_iso()))
        ledger.append(db, actor=ADMIN_ACTOR, action="CASE_CREATED",
                      payload={"case_id": args.id, "fir_no": args.fir_no, "unit": args.unit})
    print(f"Created case {args.id}.")


def cmd_add_member(args):
    _, db = _db("standard")
    with db, ledger.transaction(db):
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None or db.get(Case, args.case) is None:
            sys.exit("unknown user or case")
        db.add(CaseMember(case_id=args.case, user_id=user.id, access=args.access, granted_at=utcnow_iso(),
                          granted_by=ADMIN_ACTOR))
        ledger.append(db, actor=ADMIN_ACTOR, action="MEMBER_ADDED",
                      payload={"case_id": args.case, "username": args.username, "access": args.access})
    print(f"{args.username} is now {args.access} of {args.case}.")


def cmd_verify_ledger(args):
    _, db = _db("demo" if args.demo else "standard")
    with db:
        report = ledger.verify(db)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pramana")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--demo", action="store_true")
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("demo-reset")
    s.add_argument("--hold-back-complaints", action="store_true",
                   help="leave the three Tri-City complaints out, to upload them live (no baseline analysis)")
    s.add_argument("--yes", action="store_true", help="confirm wiping a hosted (non-SQLite) demo database")
    s.set_defaults(fn=cmd_demo_reset)
    s = sub.add_parser("verify-bundle"); s.add_argument("bundle")
    s.add_argument("--public-key", help="base64 Ed25519 public key you trust for checkpoints")
    s.set_defaults(fn=cmd_verify_bundle)
    s = sub.add_parser("checkpoint-key"); s.set_defaults(fn=cmd_checkpoint_key)
    s = sub.add_parser("init-db"); s.add_argument("--demo", action="store_true")
    s.set_defaults(fn=cmd_init_db)
    s = sub.add_parser("create-user")
    for a in ("--username", "--name", "--unit"):
        s.add_argument(a, required=True)
    s.add_argument("--role", required=True, choices=[r.value for r in Role])
    s.add_argument("--password-stdin", action="store_true")
    s.set_defaults(fn=cmd_create_user)
    s = sub.add_parser("create-case")
    for a in ("--id", "--fir-no", "--unit", "--title"):
        s.add_argument(a, required=True)
    s.add_argument("--city")
    s.set_defaults(fn=cmd_create_case)
    s = sub.add_parser("add-member")
    s.add_argument("--case", required=True); s.add_argument("--username", required=True)
    s.add_argument("--access", default="member", choices=["owner", "member"])
    s.set_defaults(fn=cmd_add_member)
    s = sub.add_parser("verify-ledger"); s.add_argument("--demo", action="store_true")
    s.set_defaults(fn=cmd_verify_ledger)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
