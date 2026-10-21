"""API of M7 (router + service) and its links with the other modules, without data or model."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import router as m07_router
from modules.m07_local_catalogue import service

from .test_search import FakeEncoder, agent  # noqa: F401  (pytest fixture)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(m07_router.router)
    return TestClient(app)


def test_mock_served_when_knowledge_base_missing(client, monkeypatch):
    monkeypatch.setattr(service, "knowledge_base_ready", lambda: False)
    out = client.post("/m07/search", json={"query": "baskets blanches à Tunis 80 TND"}).json()
    assert out["results"][0]["shop"] == "Manuella" and "mock" in out["note"]
    assert client.get("/m07/shops").json()[0]["shop"] == "Manuella"


def test_invalid_request_is_422(client):
    assert client.post("/m07/search", json={"city": "Tunis"}).status_code == 422


def test_images_only_serves_catalogue_photos(client):
    assert client.get("/m07/images/..%2F..%2Fconfig.yaml").status_code == 404
    assert client.get("/m07/images/not-a-photo.txt").status_code == 404
    assert client.get("/m07/images/0000000000000000.jpg").status_code == 404


def test_style_vector_id_resolved_through_m5(agent, monkeypatch):  # noqa: F811
    from modules.m07_local_catalogue import clients

    black = FakeEncoder().encode_texts(["black"])[0].tolist()
    monkeypatch.setattr(
        clients, "style_vector_from_m5", lambda user_id, vid: black if vid == "vec_u042" else None
    )
    out = asyncio.run(
        agent({"subcategory": "sneakers", "style_vector": "vec_u042", "user_id": "usr_042", "k": 1})
    )
    assert out["results"][0]["product_id"] == "p2" and out["note"] is None

    out = asyncio.run(agent({"subcategory": "sneakers", "style_vector": "vec_unknown"}))
    assert "M5" in out["note"] and out["results"]  # still answers, without the style part


def test_m5_mock_without_vector_gives_none():
    from modules.m07_local_catalogue.clients import style_vector_from_m5

    assert style_vector_from_m5("usr_042", "vec_u042") is None  # M5 mock has no vector yet
