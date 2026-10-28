"""A signed-in user is judged against their REAL wardrobe (M1) and wear log (M3), never the synthetic one."""

import asyncio

from modules.m06_smartbuy.agent import CONFIG, SmartBuyAgent
from modules.m06_smartbuy.memory import AgentMemory

M1_ITEMS = [
    {"item_id": "a", "category": "top", "subcategory": "shirt", "colors": [{"name": "white"}], "image_raw": "/a.png"},
    {"item_id": "b", "category": "top", "subcategory": "shirt", "colors": [{"name": "navy"}], "image_raw": "/b.png"},
    {"item_id": "c", "category": "bottom", "subcategory": "jeans", "colors": [{"name": "blue"}], "image_raw": "/c.png"},
]


def agent(tmp_path, monkeypatch, items):
    a = SmartBuyAgent({**CONFIG, "real": ["m1", "m2", "m7"], "personalize": False}, memory=AgentMemory(tmp_path))
    cl = a.clients
    monkeypatch.setattr("modules.m01_wardrobe.config.use_mocks", lambda default: False)
    monkeypatch.setattr(cl, "_m1", lambda fn, req: {"items": items})
    monkeypatch.setattr(cl, "_wears_per_year", lambda user: {"a": 40})
    return a


def run(a, **kw):
    return asyncio.run(a({"user_id": "usr_real", **kw}))


def test_owned_white_shirt_is_seen_in_the_real_wardrobe(tmp_path, monkeypatch):
    a = agent(tmp_path, monkeypatch, M1_ITEMS)
    out = run(a, probe_image="custom:shirt:white", price_tnd=90)
    assert out["sources"]["items"] == "m1" and out["sources"]["similar"] == "m1"
    assert out["similar_items"][0]["item_id"] == "a" and out["similar_items"][0]["similarity"] == 0.9
    assert out["verdict"] in ("skip", "think")
    assert "a" in a.clients.wardrobes["usr_real"]["items"][0]["id"]


def test_empty_real_wardrobe_is_not_replaced_by_the_demo_one(tmp_path, monkeypatch):
    a = agent(tmp_path, monkeypatch, [])
    out = run(a, probe_image="custom:shirt:white", price_tnd=90)
    assert out["similar_items"] == [] and out["sources"]["items"] == "m1"
