"""Week 2 against the seeded Tri-City demo: quality checks, identity review,
duplicate sources, and the graph the demo walks through."""
import json

import pytest
from fastapi.testclient import TestClient

from pramana.config import REPO_ROOT
from pramana.main import create_app

from .conftest import make_settings

DATASET = REPO_ROOT / "dataset" / "tri_city_v1"
TRUTH = json.loads((DATASET / "ground_truth.json").read_text(encoding="utf-8"))
LABELS = TRUTH["tri_city"]["labels"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    app = create_app(make_settings("demo", tmp_path_factory.mktemp("w2demo")))
    return TestClient(app)


def as_user(client, username):
    r = client.post("/demo/session", json={"username": username})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_every_planted_quality_issue_is_in_the_review_queue(demo):
    """F2 done-when: each planted issue appears before analysis runs."""
    owner_of = {c["id"]: next(m["username"] for m in c["members"] if m["access"] == "owner")
                for c in json.loads((DATASET / "cases.json").read_text(encoding="utf-8"))}
    found = set()
    for planted in TRUTH["quality_issues"]:
        cid = planted["case_id"]
        queue = demo.get(f"/cases/{cid}/review-queue", headers=as_user(demo, owner_of[cid])).json()
        found |= {(cid, q["check"]) for q in queue["quality_issues"]}
    expected = {(q["case_id"], q["issue"]) for q in TRUTH["quality_issues"]}
    assert expected <= found


def test_ambiguous_dates_need_a_stated_reading(demo):
    headers = as_user(demo, "io.mumbai")
    issue = next(q for q in demo.get("/cases/C-122/review-queue", headers=headers).json()["quality_issues"]
                 if q["check"] == "ambiguous_date_format")
    assert demo.post(f"/quality-issues/{issue['id']}/decision", headers=headers,
                     json={"reason": "checked"}).status_code == 422
    before = demo.get("/cases/C-122/timeline", headers=headers).json()
    r = demo.post(f"/quality-issues/{issue['id']}/decision", headers=headers,
                  json={"reason": "Bank confirmed US-style export", "date_order": "MDY"})
    assert r.status_code == 200
    after = demo.get("/cases/C-122/timeline", headers=headers).json()
    assert [e["ts"] for e in before] != [e["ts"] for e in after]


def test_duplicate_statement_copies_count_as_one_source(demo):
    headers = as_user(demo, "io.mumbai")
    graph = demo.get("/cases/C-107/graph", headers=headers).json()
    transfers = [e for e in graph["edges"] if e["type"] == "transferred"]
    assert transfers
    copy = "_copy_received_by_email.csv"
    checked = 0
    for e in transfers:
        sup = demo.get(f"/edges/support?ids={','.join(e['edge_ids'])}&case_id=C-107", headers=headers).json()
        files = {s["filename"] for s in sup["supports"]}
        groups = {s["source_group"] for s in sup["supports"]}
        assert sup["independent_sources"] == len(groups) == e["independent_sources"]
        if any(f.endswith(copy) for f in files):
            # The statement and its emailed copy contribute the same sources,
            # so the copy adds nothing to the count.
            copy_name = next(f for f in files if f.endswith(copy))
            original = copy_name.replace("_copy_received_by_email", "")
            from_copy = {s["source_group"] for s in sup["supports"] if s["filename"] == copy_name}
            from_original = {s["source_group"] for s in sup["supports"] if s["filename"] == original}
            assert from_copy == from_original
            without_copy = {s["source_group"] for s in sup["supports"] if s["filename"] != copy_name}
            assert len(without_copy) == e["independent_sources"]
            checked += 1
    assert checked


def test_hub_graph_and_cross_case_presence(demo):
    headers = as_user(demo, "io.mumbai")
    graph = demo.get("/cases/C-101/graph", headers=headers).json()
    hub = next(n for n in graph["nodes"] if n["label"] == LABELS["HUB"]["value"])
    assert hub["other_cases"] == ["C-102", "C-103"]
    focus = demo.get(f"/cases/C-101/graph?focus={hub['id']}&hops=1", headers=headers).json()
    labels = {n["label"] for n in focus["nodes"]}
    assert {LABELS["M1"]["value"], LABELS["M2"]["value"], LABELS["M3"]["value"], LABELS["P2P"]["value"]} <= labels
    # The same numbers, seen by the Delhi IO, never reveal C-101 or C-103.
    delhi = demo.get("/cases/C-102/graph", headers=as_user(demo, "io.delhi")).json()
    hub_d = next(n for n in delhi["nodes"] if n["label"] == LABELS["HUB"]["value"])
    assert hub_d["other_cases"] == []
    assert demo.get(f"/entities/{hub['id']}?case_id=C-101", headers=as_user(demo, "io.delhi")).status_code == 403


def test_two_rahul_sharmas_stay_separate(demo):
    """FX-01: same name, different phones and ID documents."""
    headers = as_user(demo, "io.mumbai")
    cands = demo.get("/cases/C-101/review-queue", headers=headers).json()["identity_candidates"]
    rahul = [c for c in cands if c["a_card"]["name"] == c["b_card"]["name"] == "Rahul Sharma"]
    def kinds(card):
        return {src["kind"] for src in card["sources"]}
    witness_vs_holder = next(c for c in rahul if "witness_statement" in kinds(c["a_card"]) | kinds(c["b_card"])
                             and "kyc_response" in kinds(c["a_card"]) | kinds(c["b_card"]))
    assert witness_vs_holder["suggestion"] == "likely_different"
    assert {x["type"] for x in witness_vs_holder["conflicting"]} == {"phone", "id_document"}


def test_co_signatories_and_family_phones_are_not_identity_candidates(demo):
    headers = as_user(demo, "io.mumbai")
    cands = demo.get("/cases/C-101/review-queue", headers=headers).json()["identity_candidates"]
    names = {frozenset((c["a_card"]["name"], c["b_card"]["name"])) for c in cands}
    assert frozenset(("Mahesh Agarwal", "Sunita Agarwal")) not in names
    delhi = demo.get("/cases/C-118/review-queue", headers=as_user(demo, "io.delhi")).json()
    assert all(c["a_card"]["name"] == c["b_card"]["name"] or c["name_similarity"] >= 0.85
               for c in delhi["identity_candidates"])


def test_live_upload_confirm_and_merge_flow(demo):
    """Demo steps 2 and 6: upload the C-102 complaint, confirm, then review
    the beneficiary against the bank's KYC record."""
    headers = as_user(demo, "io.mumbai")
    path = DATASET / "cases" / "C-102" / "complaint_C-102_victim.txt"
    uploaded = demo.post("/cases/C-102/evidence", headers=headers, files={"file": (path.name, path.read_bytes())},
                         data={"kind": "complaint"})
    assert uploaded.status_code == 201
    assert demo.post("/cases/C-102/extract", headers=headers).json()["extractions_created"] > 10
    queue = demo.get("/cases/C-102/review-queue", headers=headers).json()
    # The demo seed preloads a copy of this complaint (already reviewed), so
    # pick the file this test uploaded, not the first one with that name.
    f = next(x for x in queue["files"] if x["evidence_id"] == uploaded.json()["id"])
    first = f["pending_groups"][0]
    demo.post(f"/extractions/{first['sample_id']}/decision", headers=headers,
              json={"decision": "confirm", "scope": "file", "extractors": ["regex-v1", "pattern-v1"]})

    cands = demo.get("/cases/C-102/review-queue", headers=headers).json()["identity_candidates"]
    pair = next(c for c in cands if c["a_card"]["name"] == c["b_card"]["name"] == "Rahul Sharma"
                and c["suggestion"] == "merge_suggested")
    assert {"type": "bank_account", "value": LABELS["M2"]["value"]} in pair["shared"]

    assert demo.post("/identities/decision", headers=headers, json={
        "case_id": "C-102", "entity_a": pair["a"], "entity_b": pair["b"], "decision": "MERGE", "reason": "x"
    }).status_code == 422  # reason too short
    r = demo.post("/identities/decision", headers=headers, json={
        "case_id": "C-102", "entity_a": pair["a"], "entity_b": pair["b"], "decision": "MERGE",
        "reason": "Complaint beneficiary and KYC holder share account M2"})
    assert r.status_code == 200
    graph = demo.get("/cases/C-102/graph", headers=headers).json()
    rahuls = [n for n in graph["nodes"] if n["label"] == "Rahul Sharma"]
    assert len(rahuls) == 1 and rahuls[0]["merged_ids"]

    demo.post("/identities/decision", headers=headers, json={
        "case_id": "C-102", "entity_a": pair["a"], "entity_b": pair["b"], "decision": "SPLIT",
        "reason": "Undo for test"})
    graph = demo.get("/cases/C-102/graph", headers=headers).json()
    assert len([n for n in graph["nodes"] if n["label"] == "Rahul Sharma"]) == 2
