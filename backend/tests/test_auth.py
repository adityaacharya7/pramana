from sqlalchemy import select

from pramana.models import User

from .conftest import PASSWORD, entries, login, next_code


def test_login_needs_password_and_one_time_code(client, world):
    db = world
    bad_pw = client.post("/auth/login", json={"username": "io.mum", "password": "wrong password!!",
                                              "totp": next_code(db, "io.mum")})
    assert bad_pw.status_code == 401
    bad_code = client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD, "totp": "000000"})
    assert bad_code.status_code == 401
    # Identical message either way: the response never says which factor failed.
    assert bad_pw.json() == bad_code.json()

    headers = login(client, db, "io.mum")
    me = client.get("/auth/me", headers=headers).json()
    assert me["user"]["role"] == "IO" and me["user"]["unit"] == "MUM"
    assert "evidence.upload" in me["permissions"]
    assert me["build"] == "standard"


def test_one_time_code_cannot_be_replayed(client, world):
    db = world
    code = next_code(db, "io.mum")
    first = client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD, "totp": code})
    assert first.status_code == 200
    again = client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD, "totp": code})
    assert again.status_code == 401


def test_failed_logins_are_logged(client, world):
    client.post("/auth/login", json={"username": "nobody", "password": "whatever-long-pw", "totp": "123456"})
    client.post("/auth/login", json={"username": "io.mum", "password": PASSWORD, "totp": "000000"})
    failed = entries(world, "AUTH_LOGIN_FAILED")
    assert [e.actor for e in failed] == ["anonymous", "anonymous"]
    assert '"stage":"password"' in failed[0].payload and '"stage":"totp"' in failed[1].payload


def test_requests_without_a_valid_token_are_rejected(client, world):
    assert client.get("/cases").status_code == 401
    assert client.get("/cases", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_role_change_invalidates_existing_session(client, world):
    db = world
    headers = login(client, db, "io.mum")
    user = db.scalar(select(User).where(User.username == "io.mum"))
    user.role = "ANALYST"
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_standard_build_has_no_role_switcher(client, world):
    assert client.get("/demo/users").status_code == 404
    assert client.post("/demo/session", json={"username": "io.mum"}).status_code == 404
