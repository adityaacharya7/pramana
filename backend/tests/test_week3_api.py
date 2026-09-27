"""Weeks 3-5 through the API on the seeded demo: analysis scope and gates,
lead lifecycle, Challenge Mode -> reviewed apply -> stale drafts, the draft
assistant, handover export and offline re-run, blind matches and access
requests, MO comparison."""
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from pramana.config import REPO_ROOT
from pramana.main import create_app

from .conftest import entries, make_settings

TRUTH = json.loads((REPO_ROOT / "dataset" / "tri_city_v1" / "ground_truth.json").read_text(encoding="utf-8"))
L = {k: v["value"] for k, v in TRUTH["tri_city"]["labels"].items() if "value" in v}
REF = {t["id"]: t["reference"] for t in TRUTH["tri_city"]["transfers"]}


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    app = create_app(make_settings("demo", tmp_path_factory.mktemp("w3")))
    return app, TestClient(app)


def as_user(client, username):
    r = client.post("/demo/session", json={"username": username})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def lead_of(client, headers, case, rule):
    return next(l for l in client.get(f"/cases/{case}/leads", headers=headers).json() if l["rule_id"] == rule)


def test_baseline_leads_and_approved_drafts_exist(demo):
    _, c = demo
    io = as_user(c, "io.mumbai")
    rules = {l["rule_id"] for l in c.get("/cases/C-101/leads", headers=io).json()}
    assert {"CONVERGENCE-v1", "LAYERING-v1", "CASHOUT-v1", "FACILITATOR-v1", "SHARED-ID-v1", "MO-MATCH-v1"} <= rules
    conv = lead_of(c, io, "C-101", "CONVERGENCE-v1")
    detail = c.get(f"/leads/{conv['id']}", headers=io).json()
    r = detail["receipt"]
    assert r["independent_sources"] == 3 and r["unknowns"] and r["next_verification_step"]
    assert r["what_could_make_this_wrong"]["ordinary_explanation"]
    assert {d["status"] for d in detail["drafts"]} == {"APPROVED"}


def test_analysis_scope_and_gates(demo):
    app, c = demo
    io = as_user(c, "io.mumbai")
    scope = c.get("/cases/C-101/analysis-scope", headers=io).json()
    assert {"C-101", "C-102", "C-103"} <= set(scope["suggested"])
    # Open intake quality issues block analysis (spec F2: checks run before analysis).
    r = c.post("/analysis/run", headers=io, json={"case_ids": ["C-107"]})
    assert r.status_code == 409 and "quality" in r.json()["detail"]
    # Another unit's case cannot be analysed.
    assert c.post("/analysis/run", headers=as_user(c, "io.delhi"), json={"case_ids": ["C-101"]}).status_code == 403


def test_lead_lifecycle_needs_reason_and_supervisor(demo):
    app, c = demo
    io, sup = as_user(c, "io.mumbai"), as_user(c, "sup.mumbai")
    lead = lead_of(c, io, "C-101", "FACILITATOR-v1")
    assert c.post(f"/leads/{lead['id']}/transition", headers=io, json={"to": "UNDER_VERIFICATION", "reason": "x"}).status_code == 422
    r = c.post(f"/leads/{lead['id']}/transition", headers=io,
               json={"to": "UNDER_VERIFICATION", "reason": "Requesting branch records"}).json()
    assert r["result"] == "proposed" and r["status"] == "DETECTED"
    assert c.post(f"/leads/{lead['id']}/transition", headers=io,
                  json={"action": "approve", "reason": "self-approval"}).status_code == 409
    r = c.post(f"/leads/{lead['id']}/transition", headers=sup, json={"action": "approve", "reason": "Agreed"}).json()
    assert r["status"] == "UNDER_VERIFICATION"
    with app.state.sessionmaker() as db:
        change = [e for e in entries(db, "LEAD_STATUS_CHANGED") if lead["key"] in e.payload][-1]
        payload = json.loads(change.payload)
        assert payload["proposed_by"] == "io.mumbai" and payload["approved_by"] == "sup.mumbai"


def test_challenge_then_reviewed_apply_marks_drafts_stale(demo):
    """FX-31 / demo step 7."""
    app, c = demo
    io, sup, analyst = as_user(c, "io.mumbai"), as_user(c, "sup.mumbai"), as_user(c, "analyst.mumbai")
    conv = lead_of(c, io, "C-101", "CONVERGENCE-v1")
    source = f"bankref:{REF['M3-HUB']}"
    detail = c.get(f"/leads/{conv['id']}", headers=io).json()
    dep = next(s for s in detail["sources"] if s["source"] == source)
    assert {d["title"] for d in dep["dependents"]} >= {"Potential convergence point"}

    sc = c.post(f"/leads/{conv['id']}/challenge", headers=analyst,
                json={"operations": [{"op": "exclude_source", "source": source}]}).json()
    assert sc["status"] == "sandbox"
    removed = {x["rule"]: x for x in sc["diff"]["removed"]}
    assert "2 of the 3" in removed["CONVERGENCE-v1"]["why"]
    assert sc["diff"]["affected_drafts"]
    # Sandbox only: the live case and its approved drafts are untouched.
    assert {d["status"] for d in c.get(f"/leads/{conv['id']}", headers=io).json()["drafts"]} == {"APPROVED"}
    assert c.post(f"/scenarios/{sc['id']}/apply", headers=sup, json={"action": "approve", "reason": "early"}).status_code == 409
    assert c.post(f"/scenarios/{sc['id']}/apply", headers=io,
                  json={"action": "propose", "reason": "Bank withdrew this record"}).json()["status"] == "proposed"
    assert c.post(f"/scenarios/{sc['id']}/apply", headers=io, json={"action": "approve", "reason": "self"}).status_code == 409
    applied = c.post(f"/scenarios/{sc['id']}/apply", headers=sup, json={"action": "approve", "reason": "Reviewed"}).json()
    assert applied["status"] == "applied" and applied["drafts_marked_needs_reapproval"]
    after = c.get(f"/leads/{conv['id']}", headers=io).json()
    assert not after["active"] and {d["status"] for d in after["drafts"]} == {"NEEDS_REAPPROVAL"}
    with app.state.sessionmaker() as db:
        e = json.loads(entries(db, "SCENARIO_APPLIED")[-1].payload)
        assert e["proposed_by"] == "io.mumbai" and e["approved_by"] == "sup.mumbai"


def test_draft_assistant(demo):
    """F12: method stated, total within attributable, ordinary payment flagged not cleared."""
    _, c = demo
    io, sup, analyst = as_user(c, "io.mumbai"), as_user(c, "sup.mumbai"), as_user(c, "analyst.mumbai")
    lay = next(l for l in c.get("/cases/C-102/leads", headers=io).json()
               if l["rule_id"] == "LAYERING-v1" and "C-102" in l["case_ids"])
    assert c.post(f"/leads/{lay['id']}/action-drafts", headers=analyst, json={"method": "fifo"}).status_code == 403
    ds = c.post(f"/leads/{lay['id']}/action-drafts", headers=io, json={"method": "prorata"}).json()
    assert ds["within_attributable"] and ds["total"] <= ds["attributable_under_method"]
    for d in ds["drafts"]:
        assert "PRORATA" in d["draft_text"] and "Decision support only" in d["draft_text"]
        assert d["assumptions"] and d["estimate_min"] <= d["amount"] <= d["estimate_max"] + 0.01
    m2 = next(d for d in ds["drafts"] if d["account_id"] == L["M2"])
    assert any("purpose unverified" in n and "not cleared" in n for n in m2["notes"])
    detail = c.get(f"/leads/{lay['id']}", headers=io).json()
    draft = next(d for d in detail["drafts"] if d["status"] == "DRAFT")
    assert c.post(f"/action-drafts/{draft['id']}/approve", headers=io, json={"reason": "ok ok"}).status_code == 403
    assert c.post(f"/action-drafts/{draft['id']}/approve", headers=sup, json={"reason": "Checked"}).json()["status"] == "APPROVED"


def test_export_reruns_offline(demo, tmp_path):
    """F15: the bundle reproduces in a clean environment with no database."""
    _, c = demo
    io = as_user(c, "io.mumbai")
    lead = lead_of(c, io, "C-101", "CASHOUT-v1")
    bundle = c.get(f"/leads/{lead['id']}/export", headers=io).json()
    assert c.post("/bundles/verify", headers=io, json=bundle).json()["ok"]
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    run = subprocess.run([sys.executable, "-m", "pramana.cli", "verify-bundle", str(path)], capture_output=True,
                         text=True, cwd=REPO_ROOT / "backend", env={"PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    assert run.returncode == 0, run.stdout + run.stderr
    assert "REPRODUCED" in run.stdout
    bundle["input"]["transactions"][0]["amount"] += 1
    assert not c.post("/bundles/verify", headers=io, json=bundle).json()["ok"]
    pdf = c.get(f"/leads/{lead['id']}/export.pdf", headers=io)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_blind_match_and_access_request(demo):
    """F6 / FX-11: out-of-scope matches reveal only a count and the owning unit."""
    _, c = demo
    delhi = as_user(c, "io.delhi")
    matches = c.get("/cases/C-102/matches", headers=delhi).json()["matches"]
    hub = next(m for m in matches if m["value"] == L["HUB"])
    assert hub["visible_cases"] == [] and len(hub["hidden"]) == 2
    assert {h["unit"] for h in hub["hidden"]} == {"MUM-CYB", "BLR-CEN"}
    assert "C-101" not in json.dumps(hub)
    token = next(h["token"] for h in hub["hidden"] if h["unit"] == "MUM-CYB")
    req = c.post("/access-requests", headers=delhi, json={"token": token, "reason": "HUB account received C-102 funds"})
    assert req.status_code == 201 and req.json()["case_id"] is None
    rid = req.json()["id"]
    assert c.post(f"/access-requests/{rid}/decision", headers=as_user(c, "sup.delhi"),
                  json={"decision": "approve", "reason": "mine"}).status_code == 403
    r = c.post(f"/access-requests/{rid}/decision", headers=as_user(c, "sup.mumbai"),
               json={"decision": "approve", "reason": "Joint probe"}).json()
    assert r["status"] == "APPROVED"
    assert c.get("/cases/C-101", headers=delhi).status_code == 200


def test_mo_comparison_proposes_c103_with_passages(demo):
    _, c = demo
    r = c.get("/cases/C-103/mo-matches", headers=as_user(c, "io.mumbai")).json()
    top = {p["case_id"]: p for p in r["proposals"]}
    assert top["C-101"]["proposed"] and top["C-101"]["this_passages"] and top["C-101"]["other_passages"]
    assert "never evidence" in r["note"]


def test_money_trail_endpoint(demo):
    _, c = demo
    r = c.get("/cases/C-101/money-trail?cases=C-102,C-103", headers=as_user(c, "io.mumbai")).json()
    assert set(r["trail"]["methods"]) == {"fifo", "lifo", "prorata"}
    assert r["labels"] and "confidence interval" in r["note"]
