from fastapi.testclient import TestClient

from modules.m02_recommendation import mock
from modules.m02_recommendation.contract import OutfitsResponse


def test_every_mock_matches_contract():
    for fn in (mock.recommend, mock.remix, mock.complete, mock.swap, mock.score):
        out = OutfitsResponse.model_validate(fn({"user_id": "u1", "payload": {}}))
        assert out.mocked is True
        assert out.result.outfits
        for o in out.result.outfits:
            assert set(o.items) <= set(out.result.items)


def test_router_serves_mock(monkeypatch):
    from fastapi import FastAPI

    from modules.m02_recommendation.router import router

    monkeypatch.setenv("M02_USE_MOCK", "true")
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post("/m02/recommend", json={"user_id": "u1", "payload": {"context": {"occasion": "work"}}})
    assert r.status_code == 200
    body = r.json()
    assert body["mocked"] is True
    assert body["result"]["outfits"][0]["context"]["occasion"] == "work"
    r = c.post("/m02/swap", json={"payload": {"item_ids": ["m_top1"], "slot": "top"}})
    assert r.status_code == 200
