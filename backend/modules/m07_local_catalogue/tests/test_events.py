"""Search / click log (events.py): what is written, the API that feeds it, and the summary M14 reads."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import events, service
from modules.m07_local_catalogue import router as m07_router

from .test_search import agent  # noqa: F401  (pytest fixture)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(m07_router.router)
    return TestClient(app)


@pytest.fixture
def real_service(agent, monkeypatch):  # noqa: F811
    """service.search on the tiny test catalogue instead of the knowledge base."""
    monkeypatch.setattr(service, "knowledge_base_ready", lambda: True)
    monkeypatch.setattr(service, "_agent", agent)
    return service


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_search_is_logged_with_its_id(real_service, event_log):
    out = asyncio.run(real_service.search({"query": "baskets blanches à Tunis 80 TND", "user_id": "usr_1"}))
    (event,) = lines(event_log)
    assert out["search_id"] == event["event_id"] == event["target_id"]
    assert event["type"] == "local_search" and event["channel"] == "api" and event["user_id"] == "usr_1"
    assert event["value"] == "baskets blanches à Tunis 80 TND"
    data = event["data"]
    assert data["parsed"]["subcategory"] == "sneakers" and data["parsed"]["max_price_tnd"] == 80
    assert [r["product_id"] for r in data["results"]] == [r["product_id"] for r in out["results"]]
    assert data["total_matches"] == out["total_matches"] and data["latency_ms"] >= 0


def test_orchestrator_searches_are_tagged(real_service, event_log):
    asyncio.run(real_service.search({"query": "baskets noires"}, channel="orchestrator"))
    assert lines(event_log)[0]["channel"] == "orchestrator"


def test_mock_answers_are_not_logged(client, monkeypatch, event_log):
    monkeypatch.setattr(service, "knowledge_base_ready", lambda: False)
    client.post("/m07/search", json={"query": "baskets"})
    assert not event_log.exists()


def test_click_endpoint(client, event_log):
    body = {"type": "shop_click", "product_id": "p1", "search_id": "srch_1", "shop": "Shop p1", "rank": 1}
    assert client.post("/m07/events", json=body).status_code == 204
    (event,) = lines(event_log)
    assert event["type"] == "shop_click" and event["target_id"] == "p1"
    assert event["data"] == {"search_id": "srch_1", "shop": "Shop p1", "rank": 1}
    assert client.post("/m07/events", json={"type": "like", "product_id": "p1"}).status_code == 422


def test_logging_off(monkeypatch, tmp_path):
    monkeypatch.setattr(events, "log_path", lambda: None)
    events.log_click("product_view", "p1")  # nothing written, no error
    assert events.read() == []


def test_summary_for_the_dashboard(real_service, event_log):
    first = asyncio.run(real_service.search({"query": "baskets blanches à Tunis 80 TND"}))
    asyncio.run(real_service.search({"query": "sabbat ahmar"}))  # darija, nothing red in the tiny catalogue
    asyncio.run(real_service.search({"query": "bottes en daim"}))  # no boots at all: unmet demand
    top = first["results"][0]
    events.log_click("product_view", top["product_id"], first["search_id"], top["shop"], 1)
    events.log_click("shop_click", top["product_id"], first["search_id"], top["shop"], 1)

    s = events.summary(events.read())
    assert s["searches"] == 3
    assert s["zero_result_rate"] == pytest.approx(1 / 3)
    assert s["top_unmet"] == [("bottes en daim", 1)]
    assert s["darija_share"] == pytest.approx(1 / 3)
    shop = s["shops"][top["shop"]]
    assert shop["views"] == shop["clicks"] == 1 and shop["impressions"] >= 1


def test_bad_lines_are_skipped(event_log):
    event_log.write_text('not json\n{"type": "shop_click", "ts": "2026-10-15T10:00:00+00:00"}\n')
    assert len(events.read()) == 1
