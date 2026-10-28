"""F6 dashboard on simulated traffic run through the (tiny) M7 search: the injected signals are found."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m14_stylist_mode import router as m14_router
from modules.m14_stylist_mode import service
from modules.m14_stylist_mode.contract import Dashboard
from modules.m14_stylist_mode.simulate import traffic


@pytest.fixture
def simulated(isolated, m7_agent):
    """12 weeks of traffic ending now (the dashboard reads up to now)."""
    return asyncio.run(traffic.run(40, 12, seed=3, agent=m7_agent, path=isolated["sim_log"]))


def test_simulation_writes_searches_views_and_clicks(simulated, isolated):
    lines = [json.loads(x) for x in isolated["sim_log"].read_text(encoding="utf-8").splitlines()]
    assert simulated["searches"] == sum(e["type"] == "local_search" for e in lines) > 200
    assert {e["channel"] for e in lines} == {"simulated"}
    assert simulated["views"] > 0 and simulated["clicks"] > 0
    assert not isolated["real_log"].exists()  # never mixed with the real log


def test_market_dashboard_finds_the_injected_signals(simulated):
    out = Dashboard.model_validate(asyncio.run(service.get_dashboard(None, 30))).model_dump()
    assert out["simulated_share"] == 1.0 and out["n_searches"] > 50
    gold = next(t for t in out["themes"] if t["subcategory"] == "sandals" and t["color"] == "gold")
    assert gold["n_searches"] >= 50 and gold["weak_answer_rate"] == 1.0  # no gold sandals in the catalogue
    trend = next(t for t in out["trends"] if t["theme_id"] == gold["theme_id"])
    assert trend["rising"] and trend["z"] >= 2  # the wedding wave of the last 2 weeks
    unmet = next(u for u in out["unmet"] if u["theme_id"] == gold["theme_id"])
    assert unmet["products_in_market"] == 0 and unmet["opportunity"] > 0
    assert all(t["n_searches"] >= 10 for t in out["themes"])  # privacy: small groups hidden
    assert out["funnel"] is None and "silhouette" in out["method"]["themes"]


def test_shop_dashboard_hint_and_funnel(simulated):
    out = asyncio.run(service.get_dashboard("Manuella", 30))
    gold = next(u for u in out["unmet"] if "Sandals" in u["label"] and "gold" in u["label"])
    assert gold["products_in_shop"] == 0 and "0 in your shop (none in the whole catalogue)" in gold["hint"]
    assert out["funnel"]["impressions"] > 0 and out["funnel"]["rank"] is not None
    sandals = next(p for p in out["prices"] if p["subcategory"] == "sandals")
    assert sandals["shop_p50"] == 89 and 0 <= sandals["served_share"] <= 1


def test_unknown_shop_is_404_and_boutique_dashboard(simulated):
    app = FastAPI()
    app.include_router(m14_router.router)
    api = TestClient(app)
    assert api.get("/m14/dashboard", params={"shop": "Boutique inconnue"}).status_code == 404
    shop = api.post(
        "/m14/pro", json={"type": "boutique", "name": "Joliesse (demo)", "shop": "Joliesse"}
    ).json()
    out = api.get(f"/m14/pro/{shop['pro_id']}/dashboard", params={"days": 30}).json()
    assert out["shop"] == "Joliesse"
    stylist = api.post("/m14/pro", json={"type": "stylist", "name": "Amel (demo)"}).json()
    assert api.get(f"/m14/pro/{stylist['pro_id']}/dashboard").status_code == 403


def test_empty_logs_give_an_empty_dashboard():
    out = asyncio.run(service.get_dashboard(None, 30))
    assert out["n_searches"] == 0 and out["themes"] == [] and out["simulated_share"] == 0.0


def test_themes_are_kept_then_refreshed_in_the_background(simulated, monkeypatch):
    from modules.m14_stylist_mode.dashboard import themes
    from modules.m14_stylist_mode.paths import CONFIG

    monkeypatch.setitem(CONFIG["dashboard"]["themes"], "cache_minutes", 10)
    runs = []
    choose_k = themes._choose_k
    monkeypatch.setattr(themes, "_choose_k", lambda *a: runs.append(1) or choose_k(*a))

    class NowThread:  # the background refresh, run at once
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(themes.threading, "Thread", NowThread)
    market = asyncio.run(service.get_dashboard(None, 30))
    shop = asyncio.run(service.get_dashboard("Manuella", 30))  # same logs: the themes are reused
    assert len(runs) == 1 and "cache 10 min" in shop["method"]["themes"]
    assert [t["label"] for t in shop["themes"]] == [t["label"] for t in market["themes"]]
    for entry in themes._clusters.values():
        entry["at"] -= 11 * 60  # older than the cache: still shown, recomputed behind
    asyncio.run(service.get_dashboard(None, 30))
    assert len(runs) == 2


def test_a_new_request_joins_the_nearest_theme():
    import numpy as np

    from modules.m14_stylist_mode.dashboard import themes

    cfg = {"k_min": 2, "k_max": 2, "cache_minutes": 10}  # 2 requests: one theme each
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    labels, _ = themes._cluster(["red", "blue"], vectors, np.ones(2), cfg, ("logs",))
    later = np.array([[1.0, 0.0], [0.0, 1.0], [0.1, 0.9]], dtype=np.float32)
    again, method = themes._cluster(["red", "blue", "navy"], later, np.ones(3), cfg, ("logs",))
    assert list(labels) == [0, 1] and list(again) == [0, 1, 1]  # navy is nearer blue
    assert "1 new request(s) joined the nearest theme" in method
