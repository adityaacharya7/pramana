import hashlib
import json

from pramana.models import EvidenceFile

from .conftest import entries, login, tamper

STATEMENT = b"account_no,txn_time,debit,credit,balance\n123,2026-08-12 10:05:00,,78000.00,79250.00\n"


def upload(client, headers, name="statement.csv", data=STATEMENT, kind="bank_statement", case="C-1"):
    return client.post(f"/cases/{case}/evidence", headers=headers, files={"file": (name, data)}, data={"kind": kind})


def test_upload_seals_the_file_with_its_sha256(client, world):
    headers = login(client, world, "io.mum")
    r = upload(client, headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sha256"] == hashlib.sha256(STATEMENT).hexdigest()
    assert body["size_bytes"] == len(STATEMENT) and body["type"] == "CSV" and body["kind"] == "bank_statement"
    assert body["integrity_status"] == "OK" and body["duplicate_of"] is None

    logged = entries(world, "EVIDENCE_UPLOADED")
    assert len(logged) == 1
    assert json.loads(logged[0].payload)["sha256"] == body["sha256"]

    content = client.get(f"/evidence/{body['id']}/content", headers=headers)
    assert content.status_code == 200 and content.content == STATEMENT
    assert content.headers["x-evidence-sha256"] == body["sha256"]


def test_a_modified_file_is_blocked(client, world, app):
    """FX-05: a file edited after upload fails verification and is blocked."""
    headers = login(client, world, "io.mum")
    ev_id = upload(client, headers).json()["id"]
    tamper(app, ev_id, STATEMENT.replace(b"78000.00", b"7800.00"))

    verify = client.get(f"/evidence/{ev_id}/verify", headers=headers).json()
    assert verify["status"] == "MISMATCH"
    assert verify["actual_sha256"] != verify["expected_sha256"]

    blocked = client.get(f"/evidence/{ev_id}/content", headers=headers)
    assert blocked.status_code == 409
    assert "integrity mismatch" in blocked.json()["detail"].lower()
    assert len(entries(world, "EVIDENCE_INTEGRITY_MISMATCH")) == 2

    listed = client.get("/cases/C-1/evidence", headers=headers).json()
    assert listed[0]["integrity_status"] == "MISMATCH"


def test_a_deleted_file_reads_as_missing(client, world, app):
    headers = login(client, world, "io.mum")
    ev_id = upload(client, headers).json()["id"]
    tamper(app, ev_id, None)
    assert client.get(f"/evidence/{ev_id}/verify", headers=headers).json()["status"] == "MISSING"
    assert client.get(f"/evidence/{ev_id}/content", headers=headers).status_code == 409


def test_identical_copies_share_one_source_group(client, world):
    headers = login(client, world, "io.mum")
    first = upload(client, headers, name="statement.csv").json()
    copy = upload(client, headers, name="statement_copy_from_email.csv").json()
    assert copy["id"] != first["id"]
    assert copy["source_group_id"] == first["id"] and copy["duplicate_of"] == first["id"]


def test_unsupported_and_disguised_files_are_rejected(client, world):
    headers = login(client, world, "io.mum")
    assert upload(client, headers, name="photo.jpg", data=b"\xff\xd8\xff").status_code == 422
    assert upload(client, headers, name="fir.pdf", data=b"not really a pdf").status_code == 422
    assert upload(client, headers, name="blob.txt", data=b"abc\x00def").status_code == 422
    assert upload(client, headers, name="empty.txt", data=b"").status_code == 422
    assert upload(client, headers, kind="nonsense").status_code == 422
    assert upload(client, headers, name="fir.pdf", data=b"%PDF-1.7\n...").status_code == 201
    assert len(entries(world, "EVIDENCE_UPLOAD_REJECTED")) == 4
    # Nothing rejected is left in the store.
    assert world.query(EvidenceFile).count() == 1


def test_uploader_filename_never_becomes_a_path(client, world, app):
    headers = login(client, world, "io.mum")
    body = upload(client, headers, name="..\\..\\evil.txt", data=b"text").json()
    assert body["filename"] == "evil.txt"
    ev = world.get(EvidenceFile, body["id"])
    assert ev.storage_path == f"C-1/{ev.id}"


def test_oversized_upload_is_refused(client, world, app, monkeypatch):
    headers = login(client, world, "io.mum")
    settings = app.state.settings
    object.__setattr__(settings, "max_upload_bytes", 10)
    r = upload(client, headers, name="big.txt", data=b"x" * 11)
    assert r.status_code == 413
