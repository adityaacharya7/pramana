"""Week 2, standard build: extraction -> review -> graph, on small inputs."""
from pathlib import Path

from pramana.config import REPO_ROOT
from pramana.extraction import parse_file
from pramana.extraction.narrative import parse_narrative

from .conftest import entries, login, tamper

DATA = REPO_ROOT / "dataset" / "tri_city_v1" / "cases"
COMPLAINT = (DATA / "C-101" / "complaint_C-101_victim.txt").read_bytes()


def upload(client, headers, name, data, kind="complaint", case="C-1"):
    r = client.post(f"/cases/{case}/evidence", headers=headers, files={"file": (name, data)}, data={"kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


def test_every_mention_points_at_its_exact_source_text():
    text = COMPLAINT.decode()
    parsed = parse_file(text, "TXT", "g")
    assert parsed.mentions
    for m in parsed.mentions:
        assert text[m.start:m.end] == m.text
    kinds = {(m.type, m.value) for m in parsed.mentions if m.extractor in ("regex-v1", "pattern-v1")}
    assert ("bank_branch", "XSSB0000017") in kinds
    assert ("person", "Sandeep Kumar Verma") in kinds
    principal = [m for m in parsed.mentions if m.role == "principal"]
    assert [m.value for m in principal] == ["Shobha Anant Kulkarni"]


def test_name_variants_within_a_record_match_either_way_round():
    from pramana.extraction.narrative import _compatible
    for a, b in [("Shobha Anant Kulkarni", "Shobha A. Kulkarni"), ("Harish C Bhatia", "Harish Chandra Bhatia")]:
        assert _compatible(a, b) and _compatible(b, a)
    assert not _compatible("Rahul Sharma", "Rohit Sharma")
    assert not _compatible("Mahesh Agarwal", "Sunita Agarwal")


def test_complaint_relations_include_the_payment():
    text = COMPLAINT.decode()
    rels = parse_file(text, "TXT", "g").relations
    transfers = [(text[r.src[0]:r.src[1]], text[r.dst[0]:r.dst[1]], r.attrs.get("amount"))
                 for r in rels if r.type == "transferred"]
    assert len(transfers) == 1 and transfers[0][2] == 78000.0
    owns = {(text[r.src[0]:r.src[1]], r.type) for r in rels if r.type == "owns"}
    assert ("Sandeep Kumar Verma", "owns") in owns and ("Shobha Anant Kulkarni", "owns") in owns


def test_hinglish_text_does_not_go_through_the_english_model():
    text = (DATA / "C-126" / "complaint_C-126.txt").read_text(encoding="utf-8")
    parsed = parse_narrative(text, "g")
    assert not any(m.extractor.startswith("spacy") for m in parsed.mentions)
    assert any(m.type == "bank_account" for m in parsed.mentions)


def test_statement_transfers_are_grouped_by_bank_reference():
    hub = next((DATA / "C-101").glob("bank_statement_HUB_*.csv")).read_text(encoding="utf-8")
    parsed = parse_file(hub, "CSV", "g")
    assert parsed.schema == "statement"
    assert all(r.group.startswith("bankref:") for r in parsed.relations if r.type == "transferred")
    assert parsed.statement.closing == 22720.0


def test_unconfirmed_mentions_never_reach_the_graph(client, world):
    headers = login(client, world, "io.mum")
    ev = upload(client, headers, "complaint.txt", COMPLAINT)
    r = client.post("/cases/C-1/extract", headers=headers)
    assert r.status_code == 200 and r.json()["extractions_created"] > 10
    graph = client.get("/cases/C-1/graph", headers=headers).json()
    assert graph["nodes"] == [] and graph["edges"] == []

    queue = client.get("/cases/C-1/review-queue", headers=headers).json()
    groups = queue["files"][0]["pending_groups"]
    assert queue["totals"]["pending_extractions"] > 10
    sample = next(g for g in groups if g["value"] == "6048957397316")
    assert sample["snippet"]["match"] == "6048957397316"

    # Confirm every rule-based mention in the file in one decision.
    r = client.post(f"/extractions/{sample['sample_id']}/decision", headers=headers,
                    json={"decision": "confirm", "scope": "file", "extractors": ["regex-v1", "pattern-v1"]})
    assert r.status_code == 200 and r.json()["decided"] > 5
    graph = client.get("/cases/C-1/graph", headers=headers).json()
    labels = {n["label"] for n in graph["nodes"]}
    assert {"6048957397316", "Sandeep Kumar Verma", "Shobha Anant Kulkarni"} <= labels
    assert entries(world, "EXTRACTION_DECIDED")

    # Click-to-source: every edge resolves to the exact text that states it.
    text = COMPLAINT.decode()
    transfer = next(e for e in graph["edges"] if e["type"] == "transferred")
    sup = client.get(f"/edges/support?ids={','.join(transfer['edge_ids'])}&case_id=C-1", headers=headers).json()
    s, e = sup["supports"][0]["span"]
    assert "78,000" in text[s:e] and sup["supports"][0]["evidence_id"] == ev["id"]
    assert client.get(f"/evidence/{ev['id']}/text", headers=headers).text == text


def test_rejecting_a_mention_removes_what_rests_on_it(client, world):
    headers = login(client, world, "io.mum")
    upload(client, headers, "complaint.txt", COMPLAINT)
    client.post("/cases/C-1/extract", headers=headers)
    groups = client.get("/cases/C-1/review-queue", headers=headers).json()["files"][0]["pending_groups"]
    m1 = next(g for g in groups if g["value"] == "6048957397316")
    client.post(f"/extractions/{m1['sample_id']}/decision", headers=headers,
                json={"decision": "confirm", "scope": "file", "extractors": ["regex-v1", "pattern-v1"]})
    before = client.get("/cases/C-1/graph", headers=headers).json()
    assert any(e["type"] == "transferred" for e in before["edges"])
    client.post(f"/extractions/{m1['sample_id']}/decision", headers=headers,
                json={"decision": "reject", "scope": "mention"})
    after = client.get("/cases/C-1/graph", headers=headers).json()
    assert "6048957397316" not in {n["label"] for n in after["nodes"]}
    assert not any(e["type"] == "transferred" for e in after["edges"])


def test_roles_on_review_and_graph(client, world):
    io = login(client, world, "io.mum")
    upload(client, io, "complaint.txt", COMPLAINT)
    analyst = login(client, world, "analyst.mum")
    assert client.post("/cases/C-1/extract", headers=analyst).status_code == 403
    assert client.get("/cases/C-1/review-queue", headers=analyst).status_code == 403
    assert client.get("/cases/C-1/graph", headers=analyst).status_code == 200
    assert client.get("/cases/C-1/graph", headers=login(client, world, "io.del")).status_code == 403
    sup = login(client, world, "sup.mum")
    assert client.get("/cases/C-1/review-queue", headers=sup).status_code == 200


def test_tampered_file_is_not_extracted(client, world, app):
    headers = login(client, world, "io.mum")
    ev = upload(client, headers, "complaint.txt", COMPLAINT)
    tamper(app, ev["id"], COMPLAINT.replace(b"78,000", b"7,800"))
    r = client.post("/cases/C-1/extract", headers=headers).json()
    assert r["extractions_created"] == 0 and r["files_blocked"] == ["complaint.txt"]
    assert client.get(f"/evidence/{ev['id']}/text", headers=headers).status_code == 409
