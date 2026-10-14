from modules.m04_scheduler import mock
from modules.m04_scheduler.contract import Response


def test_every_mock_matches_contract():
    for name in (
        "schedule",
        "calendar",
        "event_add",
        "event_delete",
        "day",
        "tomorrow",
        "approve",
        "change",
        "wear",
        "week",
        "widget",
        "notifications",
        "notification_action",
        "run",
    ):
        out = Response.model_validate(getattr(mock, name)({"user_id": "u1", "payload": {}}))
        assert out.mocked is True


def test_router_serves_mock(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from modules.m04_scheduler.router import router

    monkeypatch.setenv("M04_USE_MOCK", "true")
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).post("/m04/today", json={"user_id": "u1", "payload": {}})
    assert r.status_code == 200 and r.json()["mocked"] is True
