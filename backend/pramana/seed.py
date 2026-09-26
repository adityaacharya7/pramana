"""Load the synthetic dataset into the demo build's database."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ledger
from .config import Settings
from .db import utcnow_iso
from .models import Case, CaseMember, Deployment, EvidenceFile, Extraction, User
from .routers.evidence import seal
from .security import new_totp_secret

SYSTEM = "system:demo-seed"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_demo(db: Session, settings: Settings, preload_all: bool = False) -> dict:
    if not settings.is_demo:
        raise RuntimeError("The synthetic dataset is only ever loaded into the demo build.")
    ds = settings.dataset_dir
    manifest = _load(ds / "manifest.json")
    if not manifest.get("synthetic"):
        raise RuntimeError("Refusing to seed from a dataset not marked synthetic.")
    users, cases = _load(ds / "demo_users.json"), _load(ds / "cases.json")
    now = utcnow_iso()

    with ledger.transaction(db):
        db.get(Deployment, 1).dataset = manifest["dataset"]
        ledger.append(db, actor=SYSTEM, action="DEMO_SEEDED", payload={
            "dataset": manifest["dataset"], "seed": manifest["seed"],
            "generator_version": manifest["generator_version"],
        })
        by_name: dict[str, User] = {}
        for u in users:
            # Demo users sign in through the role switcher only: no password.
            # A TOTP secret is still set so the same code paths hold.
            user = User(username=u["username"], name=u["name"], role=u["role"], unit=u["unit"],
                        password_hash=None, totp_secret=new_totp_secret(), created_at=now)
            db.add(user)
            by_name[u["username"]] = user
        db.flush()
        for u in by_name.values():
            ledger.append(db, actor=SYSTEM, action="USER_CREATED",
                          payload={"username": u.username, "role": u.role, "unit": u.unit})
        for c in cases:
            db.add(Case(id=c["id"], fir_no=c["fir_no"], unit=c["unit"], city=c["city"], status=c["status"],
                        title=c["title"], station=c["station"], registered_on=c["registered_on"],
                        complainant=c["complainant"], created_at=now))
            db.flush()
            for m in c["members"]:
                db.add(CaseMember(case_id=c["id"], user_id=by_name[m["username"]].id, access=m["access"],
                                  granted_at=now, granted_by=SYSTEM))
            ledger.append(db, actor=SYSTEM, action="CASE_CREATED", payload={
                "case_id": c["id"], "fir_no": c["fir_no"], "unit": c["unit"],
                "members": [f"{m['username']}:{m['access']}" for m in c["members"]],
            })

    owners = {c["id"]: next(m["username"] for m in c["members"] if m["access"] == "owner") for c in cases}
    loaded, held_back = 0, []
    for f in manifest["files"]:
        if not f["case_id"]:
            continue
        if f.get("demo_live_upload") and not preload_all:
            held_back.append(f["path"])
            continue
        owner = db.scalar(select(User).where(User.username == owners[f["case_id"]]))
        with open(ds / f["path"], "rb") as fh:
            ev = seal(db, settings, case_id=f["case_id"], stream=fh, filename=Path(f["path"]).name,
                      kind=f["kind"], uploaded_by=owner, actor=SYSTEM,
                      extra={"preloaded": True, "on_behalf_of": owner.username})
        if ev.sha256 != f["sha256"]:
            raise RuntimeError(f"Dataset file {f['path']} does not match its manifest hash.")
        loaded += 1

    reviewed = baseline_review(db, settings, owners)
    return {"users": len(users), "cases": len(cases), "evidence_loaded": loaded,
            "held_back_for_live_upload": held_back, "baseline_review": reviewed}


def baseline_review(db: Session, settings: Settings, owners: dict[str, str]) -> dict:
    """Preloaded evidence arrives in the demo already reviewed, as it would in
    a case worked for some days: extraction runs, and the deterministic
    mentions (identifier rules, role patterns, spreadsheet columns) are
    confirmed on behalf of the owning IO. Model (NER) suggestions stay
    pending for an officer, and identity and quality questions stay open."""
    from .extraction import engine

    totals = {"extractions": 0, "confirmed": 0, "left_pending": 0}
    for case_id, owner_name in sorted(owners.items()):
        owner = db.scalar(select(User).where(User.username == owner_name))
        with ledger.transaction(db):
            summary = engine.run_extraction(db, settings, case_id)
            files = db.scalars(select(EvidenceFile).where(EvidenceFile.case_id == case_id)).all()
            confirmed = 0
            for ev in files:
                pending = db.scalars(select(Extraction).where(Extraction.file_id == ev.id,
                                                              Extraction.status == "PENDING",
                                                              Extraction.extractor.in_(engine.DETERMINISTIC))).all()
                engine.decide(db, owner.id, case_id, pending, "CONFIRMED")
                engine.derive_file(db, settings, ev)
                confirmed += len(pending)
            ledger.append(db, actor=SYSTEM, action="EXTRACTION_RUN", payload={
                "case_id": case_id, "files": summary["files_processed"],
                "extractions_created": summary["extractions_created"], "by_type": summary["by_type"],
                "quality_issues_open": summary["quality_issues_open"],
            })
            ledger.append(db, actor=SYSTEM, action="BASELINE_REVIEW_APPLIED", payload={
                "case_id": case_id, "on_behalf_of": owner.username, "confirmed": confirmed,
                "scope": "deterministic extractors only: " + ", ".join(engine.DETERMINISTIC),
            })
        totals["extractions"] += summary["extractions_created"]
        totals["confirmed"] += confirmed
    totals["left_pending"] = totals["extractions"] - totals["confirmed"]
    return totals


def is_seeded(db: Session) -> bool:
    return db.scalar(select(User).limit(1)) is not None


def evidence_count(db: Session) -> int:
    return len(db.scalars(select(EvidenceFile.id)).all())
