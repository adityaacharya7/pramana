"""The AI endpoints see only what the signed-in user could open themselves,
and case registration follows the permission matrix."""
import json

import pytest

from pramana import ai

from .conftest import PASSWORD, entries, login, make_case


@pytest.fixture
def prompts(monkeypatch):
    """Replace the Gemini call; record every prompt and system instruction."""
    seen: list[str] = []

    def fake_call(prompt, system_instruction=None, response_json=False, **_):
        seen.append(f"{system_instruction or ''}\n{prompt}")
        if response_json:
            return json.dumps({"typology": "t", "risk_score": 1, "confidence": "LOW", "summary": "s",
                               "modus_operandi": [], "statutory_sections": [], "syndicate_hierarchy": [],
                               "immediate_actions": []})
        return "ok"

    monkeypatch.setattr(ai, "call_gemini", fake_call)
    return seen


@pytest.fixture
def cities(world):
    make_case(world, "C-101", "MUM", {"io.mum": "owner"})
    make_case(world, "C-202", "DEL", {"io.del": "owner"})
    return world


def test_chat_on_an_out_of_scope_case_is_refused_and_logged(client, cities, prompts):
    headers = login(client, cities, "io.mum")
    r = client.post("/ai/chat", headers=headers, json={"message": "summarise", "case_id": "C-202"})
    assert r.status_code == 403
    assert prompts == []
    refused = entries(cities, "ACCESS_REFUSED")
    assert refused[-1].case_id == "C-202"


def test_chat_ignores_out_of_scope_cases_named_in_the_message(client, cities, prompts):
    headers = login(client, cities, "io.mum")
    r = client.post("/ai/chat", headers=headers, json={"message": "Compare C-101 with C-202"})
    assert r.status_code == 200
    sent = "\n".join(prompts)
    assert "[C-101]" in sent
    assert "C-202/2026" not in sent and "[C-202]" not in sent


def test_prompts_carry_no_dataset_answer_key(client, cities, prompts):
    headers = login(client, cities, "io.mum")
    client.post("/ai/chat", headers=headers, json={"message": "who is behind this?", "case_id": "C-101"})
    client.post("/ai/case-analysis", headers=headers, json={"case_id": "C-101"})
    sent = "\n".join(prompts)
    for planted in ("Vivek Chauhan", "Shree Balaji Traders", "563551302754", "6577461070", "Aakash Jain"):
        assert planted not in sent


def test_case_analysis_and_notice_follow_the_matrix(client, cities, prompts):
    io_del = login(client, cities, "io.del")
    assert client.post("/ai/case-analysis", headers=io_del, json={"case_id": "C-101"}).status_code == 403
    notice = {"case_id": "C-101", "entity_name": "Nodal Officer", "entity_identifier": "123"}
    assert client.post("/ai/draft-notice", headers=io_del, json=notice).status_code == 403
    analyst = login(client, cities, "analyst.mum")
    assert client.post("/ai/draft-notice", headers=analyst, json={**notice, "case_id": "C-1"}).status_code == 403
    io_mum = login(client, cities, "io.mum")
    r = client.post("/ai/draft-notice", headers=io_mum, json=notice)
    assert r.status_code == 200
    assert "78,000" not in prompts[-1] and "[not provided]" in prompts[-1]


def test_login_has_no_master_codes_or_default_passwords(client, world):
    for code in ("000000", "123456", "999999"):
        r = client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD, "totp": code})
        assert r.status_code == 401
    assert client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD}).status_code == 422
    for pw in ("Pramana@2026", "password", "admin123"):
        r = client.post("/auth/login", json={"username": "io.mum", "password": pw, "totp": "123456"})
        assert r.status_code == 401


def test_case_registration_is_role_gated_and_in_own_unit(client, world):
    body = {"fir_no": "9/2026", "title": "New complaint", "complainant": "A", "unit": "DEL"}
    for username in ("auditor", "admin", "analyst.mum"):
        assert client.post("/cases", headers=login(client, world, username), json=body).status_code == 403
    first = client.post("/cases", headers=login(client, world, "io.mum"), json=body)
    assert first.status_code == 201
    assert first.json()["unit"] == "MUM"
    second = client.post("/cases", headers=login(client, world, "sup.mum"), json=body)
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
