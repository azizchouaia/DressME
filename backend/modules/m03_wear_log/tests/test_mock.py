from modules.m03_wear_log import mock
from modules.m03_wear_log.contract import Response


def test_every_mock_matches_contract():
    for fn in (
        mock.worn,
        mock.unworn,
        mock.posted,
        mock.status,
        mock.laundry_done,
        mock.states,
        mock.stats,
        mock.history,
        mock.forgotten,
        mock.recap,
    ):
        out = Response.model_validate(fn({"user_id": "u1", "payload": {}}))
        assert out.mocked is True and out.result


def test_router_serves_mock(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from modules.m03_wear_log.router import router

    monkeypatch.setenv("M03_USE_MOCK", "true")
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).post("/m03/worn", json={"user_id": "u1", "payload": {"item_ids": ["a", "b"]}})
    assert r.status_code == 200 and r.json()["mocked"] is True
