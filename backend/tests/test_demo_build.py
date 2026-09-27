import json

import pytest
from sqlalchemy import select

from pramana import ledger
from pramana.config import REPO_ROOT, load_settings
from pramana.db import DeploymentMismatch
from pramana.main import create_app
from pramana.models import Case, EvidenceFile, User
from fastapi.testclient import TestClient

from .conftest import make_settings

DATASET = REPO_ROOT / "dataset" / "tri_city_v1"


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    app = create_app(make_settings("demo", tmp_path_factory.mktemp("demo")))
    return app, TestClient(app)


def as_user(client, username):
    r = client.post("/demo/session", json={"username": username})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demo_build_is_seeded_from_the_synthetic_dataset(demo):
    app, client = demo
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    live = {f["path"].split("/")[-1] for f in manifest["files"] if f.get("demo_live_upload")}
    with app.state.sessionmaker() as db:
        assert db.query(User).count() == 9
        assert db.query(Case).count() == 30
        stored = db.scalars(select(EvidenceFile)).all()
        # Everything, including the three Tri-City complaints (use
        # `demo-reset --hold-back-complaints` to upload those live instead).
        assert len(stored) == sum(1 for f in manifest["files"] if f["case_id"])
        assert live <= {e.filename for e in stored}
        # Seeded files carry the dataset's own hashes.
        by_name = {f["path"].split("/")[-1]: f["sha256"] for f in manifest["files"]}
        assert all(e.sha256 == by_name[e.filename] for e in stored)
        assert ledger.verify(db)["ok"]


def test_role_switcher_lists_roles_and_issues_sessions(demo):
    _, client = demo
    users = client.get("/demo/users").json()
    assert {u["role"] for u in users} == {"IO", "ANALYST", "SUPERVISOR", "AUDITOR", "ADMIN"}
    me = client.get("/auth/me", headers=as_user(client, "sup.mumbai")).json()
    assert me["build"] == "demo" and me["user"]["role"] == "SUPERVISOR"


def test_tri_city_joint_probe_scope(demo):
    _, client = demo
    mumbai = [c["id"] for c in client.get("/cases", headers=as_user(client, "io.mumbai")).json()]
    assert {"C-101", "C-102", "C-103"} <= set(mumbai)
    delhi_io = as_user(client, "io.delhi")
    delhi = [c["id"] for c in client.get("/cases", headers=delhi_io).json()]
    assert "C-102" in delhi and "C-101" not in delhi
    assert client.get("/cases/C-101", headers=delhi_io).status_code == 403


def test_demo_io_can_upload_a_tri_city_complaint(demo):
    _, client = demo
    path = DATASET / "cases" / "C-101" / "complaint_C-101_victim.txt"
    r = client.post("/cases/C-101/evidence", headers=as_user(client, "io.mumbai"),
                    files={"file": (path.name, path.read_bytes())}, data={"kind": "complaint"})
    assert r.status_code == 201
    assert r.json()["duplicate_of"]  # already preloaded: a byte-identical copy, one source
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    expected = next(f["sha256"] for f in manifest["files"] if f["path"].endswith(path.name))
    assert r.json()["sha256"] == expected


def test_standard_build_refuses_the_demo_database(demo, monkeypatch):
    app, _ = demo
    monkeypatch.setenv("PRAMANA_DB_URL", app.state.settings.db_url)
    settings = load_settings("standard", data_root=app.state.settings.data_dir.parent)
    with pytest.raises(DeploymentMismatch):
        create_app(settings)
