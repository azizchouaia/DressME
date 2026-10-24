"""BO6 Selected 6 (3D try-on through BO9) and Backup 2 (loyalty codes of the shops) on the M7 side.

BO9's 3D service is simulated until `m9` is listed in config.yaml `real`; the real path is tested here with a
fake service. Loyalty codes come from the boutique accounts of M14 (same BO), a temporary folder here.
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import clients, service
from modules.m07_local_catalogue import router as m07_router
from modules.m07_local_catalogue.contract import TryOnInput
from modules.m07_local_catalogue.paths import CONFIG
from shared.base_agent import AgentError

from .test_search import agent  # noqa: F401  (fixture: tiny catalogue, fake encoder)


def try_on(a, **payload):
    return asyncio.run(a.try_on(TryOnInput(**payload))).model_dump()


# ---- Selected 6: a local piece on the avatar
def test_try_on_is_simulated_until_bo9_is_connected(agent):  # noqa: F811
    out = try_on(agent, product_id="p5")
    assert out["model_url"] is None and out["sources"] == {"m9": "mock"}
    assert out["note"].startswith("Simulation : le service 3D du BO9")
    assert (out["category"], out["subcategory"]) == ("top", "shirt")
    with pytest.raises(AgentError, match="unknown product_id"):
        try_on(agent, product_id="nope")


def test_try_on_with_bo9_builds_and_serves_the_glb(agent, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setitem(CONFIG, "real", ["m9"])
    sent = []

    class Answer:
        content = b"glTF-binary-model"

        def raise_for_status(self):
            return None

    def fake_post(url, content, headers, timeout):
        sent.append((url, headers["X-TripoSR-Resolution"]))
        return Answer()

    image = tmp_path / "p5.jpg"
    image.write_bytes(b"jpeg")
    monkeypatch.setattr(clients.httpx, "post", fake_post)
    monkeypatch.setattr("modules.m07_local_catalogue.agent.IMAGES_DIR", tmp_path)
    out = try_on(agent, product_id="p5", language="en")
    assert out["model_url"] == "/m07/try-on/p5.glb" and out["sources"] == {"m9": "real"}
    assert sent == [("http://127.0.0.1:8766/reconstruct", "256")]
    assert out["note"].startswith("3D model ready")

    monkeypatch.setattr(service, "knowledge_base_ready", lambda: True)
    monkeypatch.setattr(service, "_agent", agent)
    app = FastAPI()
    app.include_router(m07_router.router)
    api = TestClient(app)
    glb = api.get("/m07/try-on/p5.glb")
    assert glb.status_code == 200 and glb.content == b"glTF-binary-model"
    assert api.get("/m07/try-on/p4.glb").status_code == 404
    again = api.post("/m07/try-on", json={"product_id": "p5"}).json()  # cached: BO9 is not called again
    assert again["model_url"] == "/m07/try-on/p5.glb" and len(sent) == 1


def test_try_on_next_action_names_the_skill(agent):  # noqa: F811
    acts = {a["action"]: a for a in asyncio.run(agent({"query": "chemise en lin blanche"}))["next_actions"]}
    assert acts["try_on"]["tool"] == "tryon" and acts["try_on"]["args"]["endpoint"] == "/m07/try-on"


# ---- Backup 2: the shop's loyalty code on its pieces
def test_a_shop_with_a_loyalty_code_shows_it(agent):  # noqa: F811
    from modules.m14_stylist_mode import store

    store.pros.put(
        "pro_b",
        {
            "pro_id": "pro_b",
            "type": "boutique",
            "name": "Shop p5",
            "shop": "Shop p5",
            "loyalty": {"code": "LIN10", "discount_pct": 10, "until": None, "conditions": None},
            "created_at": "2026-10-24T10:00:00+00:00",
        },
    )
    store.pros.put(
        "pro_old",
        {
            "pro_id": "pro_old",
            "type": "boutique",
            "name": "Shop p1",
            "shop": "Shop p1",
            "loyalty": {"code": "OLD5", "discount_pct": 5, "until": "2020-01-01", "conditions": None},
            "created_at": "2026-10-24T10:00:00+00:00",
        },
    )
    out = asyncio.run(agent({"query": "chemise en lin blanche"}))
    top = out["results"][0]
    assert top["loyalty"]["code"] == "LIN10" and "Code fidélité LIN10 : −10 %" in top["reasons"]
    sneakers = asyncio.run(agent({"query": "baskets blanches", "language": "en"}))
    assert all(r["loyalty"] is None for r in sneakers["results"])  # Shop p1's code has expired
