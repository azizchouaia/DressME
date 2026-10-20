"""TestClient on every M1 endpoint (mock mode) + the demo UI."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m01_wardrobe.contract import EMBEDDING_DIM
from modules.m01_wardrobe.router import router

from .helpers import png_b64

DEMO = "usr_demo"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_router_is_mounted_by_the_gateway():
    from api.main import app

    paths = {r.path for r in app.routes}
    assert {"/m01/classify", "/m01/similar", "/m01/duplicates", "/m01/items", "/m01/items/{item_id}",
            "/m01/items/{item_id}/confirm", "/m01/ui"} <= paths


@pytest.mark.parametrize(
    ("env", "global_mocks", "expected"),
    [(None, True, "mock"), (None, False, "service"), ("false", True, "service"), ("true", False, "mock"),
     ("0", True, "service"), ("", False, "service")],
)
def test_m01_use_mocks_overrides_the_global_setting(monkeypatch, env, global_mocks, expected):
    from modules.m01_wardrobe import router as m01_router
    from shared.config import settings

    if env is not None:
        monkeypatch.setenv("M01_USE_MOCKS", env)
    monkeypatch.setattr(settings, "use_mocks", global_mocks)
    assert m01_router._impl().__name__.endswith(expected)


def test_items(client):
    r = client.post("/m01/items", json={"user_id": DEMO})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 13 and body["mocked"] is True
    assert {i["shelf"] for i in body["items"]} == {"accessories", "clothes", "shoes"}


def test_items_filter_and_validation(client):
    r = client.post("/m01/items", json={"user_id": DEMO, "category": "accessory"})
    assert r.json()["total"] == 3
    assert client.post("/m01/items", json={"user_id": DEMO, "category": "hat"}).status_code == 422
    assert client.post("/m01/items", json={}).status_code == 422


def test_get_and_delete_item(client):
    r = client.get("/m01/items/itm_demo_loafers", params={"user_id": DEMO})
    assert r.status_code == 200 and r.json()["category"] == "shoes"
    assert client.get("/m01/items/itm_demo_loafers", params={"user_id": "someone_else"}).status_code == 404
    assert client.get("/m01/items/itm_demo_loafers").status_code == 422          # user_id required
    r = client.delete("/m01/items/itm_demo_loafers", params={"user_id": DEMO})
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert client.delete("/m01/items/itm_demo_loafers", params={"user_id": DEMO}).status_code == 404


def test_similar(client):
    r = client.post("/m01/similar", json={"user_id": DEMO, "item_id": "itm_demo_shirt_navy", "k": 3})
    assert r.status_code == 200
    assert r.json()["neighbours"][0]["item_id"] == "itm_demo_shirt_navy_2"
    assert client.post("/m01/similar", json={"user_id": DEMO}).status_code == 422
    assert client.post("/m01/similar", json={"user_id": DEMO, "item_id": "nope"}).status_code == 404


def test_duplicates(client):
    r = client.post("/m01/duplicates", json={"user_id": DEMO})
    assert r.status_code == 200
    assert r.json()["groups"] == [["itm_demo_shirt_navy", "itm_demo_shirt_navy_2"]]
    r = client.post("/m01/duplicates", json={"user_id": DEMO, "threshold": 0.99})
    assert r.json()["groups"] == []


def test_classify_then_media_is_served(client):
    r = client.post("/m01/classify", json={"user_id": DEMO, "image": png_b64(data_url=True)})
    assert r.status_code == 200
    body = r.json()
    assert body["stored"] is True and len(body["embedding"]) == EMBEDDING_DIM
    assert set(body) >= {"garment", "embedding", "needs_confirmation", "duplicates", "stored"}
    media = client.get(body["garment"]["image_raw"])
    assert media.status_code == 200 and media.headers["content-type"] == "image/png"
    assert client.post("/m01/items", json={"user_id": DEMO}).json()["total"] == 14


def test_duplicate_confirm_and_cancel_over_http(client):
    image = png_b64(color=(120, 60, 200), data_url=True)
    assert client.post("/m01/classify", json={"user_id": DEMO, "image": image}).json()["stored"] is True
    held = client.post("/m01/classify", json={"user_id": DEMO, "image": image}).json()
    assert held["pending"] is True and held["stored"] is False and held["duplicates"]
    item_id = held["garment"]["item_id"]
    assert client.post("/m01/items", json={"user_id": DEMO}).json()["total"] == 14       # hidden
    assert client.get(f"/m01/items/{item_id}", params={"user_id": DEMO}).json()["status"] == "pending"

    r = client.post(f"/m01/items/{item_id}/confirm", params={"user_id": DEMO})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert client.post("/m01/items", json={"user_id": DEMO}).json()["total"] == 15
    assert client.post(f"/m01/items/{item_id}/confirm", params={"user_id": DEMO}).status_code == 404

    held_again = client.post("/m01/classify", json={"user_id": DEMO, "image": image}).json()
    assert held_again["pending"] is True
    cancel_url = "/m01/items/" + held_again["garment"]["item_id"]
    assert client.delete(cancel_url, params={"user_id": DEMO}).status_code == 200
    assert client.post("/m01/items", json={"user_id": DEMO}).json()["total"] == 15
    assert client.post("/m01/items/nope/confirm", params={"user_id": DEMO}).status_code == 404


def test_classify_bad_image(client):
    r = client.post("/m01/classify", json={"user_id": DEMO, "image": "definitely not an image"})
    assert r.status_code == 422
    r = client.post("/m01/classify", json={"user_id": DEMO, "image": png_b64(), "mode": "nope"})
    assert r.status_code == 422


def test_ui_and_assets(client):
    r = client.get("/m01/ui")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Ouvrir ma garde-robe" in r.text
    for path in ("/m01/ui/styles.css", "/m01/ui/app.js", "/m01/ui/assets/shirt-navy.svg"):
        assert client.get(path).status_code == 200, path
    assert client.get("/m01/ui/").status_code == 200                 # redirect followed


def test_every_demo_image_exists(client):
    for item in client.post("/m01/items", json={"user_id": DEMO}).json()["items"]:
        assert client.get(item["image_raw"]).status_code == 200, item["image_raw"]


def test_static_routes_block_path_traversal(client):
    assert client.get("/m01/ui/../router.py").status_code == 404
    assert client.get("/m01/ui/%2e%2e/router.py").status_code == 404
    assert client.get("/m01/media/../../config.yaml").status_code == 404
    assert client.get("/m01/ui/missing.css").status_code == 404
