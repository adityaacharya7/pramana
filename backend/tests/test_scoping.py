import json

from .conftest import entries, login


def test_io_requesting_another_units_case_gets_403_and_a_ledger_entry(client, world):
    """F1 done-when."""
    headers = login(client, world, "io.mum")
    r = client.get("/cases/C-2", headers=headers)
    assert r.status_code == 403
    refused = entries(world, "ACCESS_REFUSED")
    assert len(refused) == 1
    payload = json.loads(refused[0].payload)
    assert refused[0].actor == "io.mum"
    assert payload["case_id"] == "C-2" and payload["attempted"] == "case.view"
    assert refused[0].case_id == "C-2"


def test_case_list_is_scoped_by_membership_and_unit(client, world):
    def ids(username):
        return [c["id"] for c in client.get("/cases", headers=login(client, world, username)).json()]

    assert ids("io.mum") == ["C-1"]
    assert ids("io.del") == ["C-2"]
    assert ids("analyst.mum") == ["C-1"]
    assert ids("sup.mum") == ["C-1"]  # unit cases only; Delhi needs an access request
    assert ids("auditor") == []  # reads the ledger, not case content
    assert ids("admin") == []  # no case content access


def test_supervisor_reaches_unit_cases_without_membership(client, world):
    headers = login(client, world, "sup.mum")
    r = client.get("/cases/C-1", headers=headers)
    assert r.status_code == 200
    assert r.json()["my_access"] == "unit"
    assert client.get("/cases/C-2", headers=headers).status_code == 403


def test_only_an_io_on_the_case_can_upload(client, world):
    files = {"file": ("note.txt", b"statement text", "text/plain")}
    for username in ("analyst.mum", "sup.mum", "io.del"):
        r = client.post("/cases/C-1/evidence", headers=login(client, world, username), files=files)
        assert r.status_code == 403, username
    assert len(entries(world, "ACCESS_REFUSED")) == 3
    r = client.post("/cases/C-1/evidence", headers=login(client, world, "io.mum"), files=files)
    assert r.status_code == 201


def test_unknown_case_is_404_not_403(client, world):
    assert client.get("/cases/C-999", headers=login(client, world, "io.mum")).status_code == 404


def test_ledger_read_is_limited_by_role_and_scope(client, world):
    client.get("/cases/C-2", headers=login(client, world, "io.mum"))  # logs a refusal on C-2
    assert client.get("/ledger", headers=login(client, world, "analyst.mum")).status_code == 403
    all_entries = client.get("/ledger", headers=login(client, world, "auditor")).json()
    assert any(e["case_id"] == "C-2" for e in all_entries)
    mum = client.get("/ledger", headers=login(client, world, "sup.mum")).json()
    assert all(e["case_id"] == "C-1" for e in mum)
