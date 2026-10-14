from modules.m17_capsule import mock
from modules.m17_capsule.contract import CapsuleResponse


def test_mock_matches_contract():
    for fn in (mock.capsule, mock.plan_capsule):
        out = CapsuleResponse.model_validate(fn({"user_id": "u1", "payload": {}}))
        assert out.mocked is True and out.result["n_outfits"] == len(out.result["outfits"])


def test_router_serves_mock(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from modules.m17_capsule.router import router

    monkeypatch.setenv("M17_USE_MOCK", "true")
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).post("/m17/capsule", json={"user_id": "u1", "payload": {"size": 12}})
    assert r.status_code == 200 and r.json()["mocked"] is True
