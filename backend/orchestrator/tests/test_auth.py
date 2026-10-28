"""Sign up, sign in, profile, demo account."""

from fastapi.testclient import TestClient

from api.main import app

c = TestClient(app)


def test_register_login_me(tmp_path, monkeypatch):
    from api.routes import auth
    monkeypatch.setattr(auth, "STORE", tmp_path / "users.json")
    r = c.post("/auth/register", json={"name": "Sarra", "email": "Sarra@Mail.tn", "password": "secret1"})
    assert r.status_code == 201
    uid = r.json()["user"]["user_id"]
    assert c.post("/auth/register", json={"name": "x", "email": "sarra@mail.tn", "password": "secret1"}).status_code == 409
    assert c.post("/auth/login", json={"email": "sarra@mail.tn", "password": "nope00"}).status_code == 401
    tok = c.post("/auth/login", json={"email": "sarra@mail.tn", "password": "secret1"}).json()["token"]
    me = c.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["user_id"] == uid and "hash" not in me and "salt" not in me
    assert c.patch("/auth/me", json={"city": "Sfax"}, headers={"Authorization": f"Bearer {tok}"}).json()["city"] == "Sfax"
    assert c.get("/auth/me").status_code == 401
    assert c.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_demo_account_exists(tmp_path, monkeypatch):
    from api.routes import auth
    monkeypatch.setattr(auth, "STORE", tmp_path / "users.json")
    r = c.post("/auth/login", json={"email": "demo@dressme.tn", "password": "demo1234"})
    assert r.status_code == 200 and r.json()["user"]["user_id"] == "usr_demo"
