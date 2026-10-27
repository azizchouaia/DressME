"""Extras: wishlist price watch, cheaper look-alikes, wear check-in -> real labels."""

import asyncio
from datetime import datetime, timedelta

import pytest

from modules.m06_smartbuy import extras
from modules.m06_smartbuy.agent import CONFIG, SmartBuyAgent
from modules.m06_smartbuy.memory import AgentMemory

SHOPS = [
    {"name": "A", "city": "Tunis", "items": [
        {"name": "White shirt", "subcategory": "shirt", "colour": "white", "price_tnd": 60, "url": "a/1", "product_id": "p1"},
        {"name": "Beige shirt", "subcategory": "shirt", "colour": "beige", "price_tnd": 50, "url": "a/2"}]},
    {"name": "B", "city": "Sfax", "items": [
        {"name": "White shirt", "subcategory": "shirt", "colour": "white", "price_tnd": 95, "url": "b/1"},
        {"name": "Red shirt", "subcategory": "shirt", "colour": "red", "price_tnd": 30, "url": "b/2"}]},
]


@pytest.fixture()
def mem(tmp_path):
    return AgentMemory(tmp_path)


def test_wishlist_alert_when_price_under_target(mem):
    w = extras.wishlist_add(mem, "u", "shirt", "white", 100)
    assert w["target_tnd"] == 85
    alerts = extras.wishlist_check(mem, "u", SHOPS)
    assert len(alerts) == 1 and alerts[0]["now_tnd"] == 60 and alerts[0]["saved_tnd"] == 40
    assert alerts[0]["next_action"]["tool"] == "smartbuy"
    assert extras.wishlist_check(mem, "u", SHOPS) == []          # no spam: same price, no new alert


def test_wishlist_no_alert_above_target_and_remove(mem):
    w = extras.wishlist_add(mem, "u", "shirt", "white", 65)        # target 55.2, best is 60
    assert extras.wishlist_check(mem, "u", SHOPS) == []
    assert extras.wishlist_remove(mem, "u", w["id"]) and extras.wishlist(mem, "u") == []


def test_alternatives_cheaper_same_colour_first_one_per_shop():
    alts = extras.alternatives(SHOPS, "shirt", "white", 100)
    assert [a["shop"] for a in alts] == ["A"]          # B: white is too dear, red is too far
    assert alts[0]["colour"] == "white" and alts[0]["saved_pct"] == 40
    assert all(a["colour"] != "red" for a in alts)                  # far colour is not a look-alike
    assert extras.alternatives(SHOPS, "shirt", "white", 55) == []    # nothing 15% cheaper


@pytest.mark.parametrize("text,times,regret", [
    ("twice", 2, False), ("jamais", 0, False), ("barcha", 8, False), ("3 times but too tight", 3, True),
    ("une fois", 1, False), ("5", 5, False), ("ma lbesthech", 0, False)])
def test_parse_wear(text, times, regret, monkeypatch):
    monkeypatch.setattr(extras, "_parse_wear_llm", lambda *a, **k: None)
    p = extras.parse_wear(text)
    assert p["times_worn"] == times and p["regret"] == regret


def test_wear_label():
    assert extras.wear_label(0, False) == "skip"
    assert extras.wear_label(5, True) == "skip"
    assert extras.wear_label(1, False) == "think"
    assert extras.wear_label(4, False) == "buy"


def test_checkin_flow_gives_real_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(extras, "_parse_wear_llm", lambda *a, **k: None)
    agent = SmartBuyAgent({**CONFIG, "real": [], "personalize": False}, memory=AgentMemory(tmp_path))
    out = asyncio.run(agent({"user_id": "usr_sarra", "probe_image": next(iter(agent.clients.candidates)), "price_tnd": 80}))
    agent.feedback("usr_sarra", out["decision_id"], bought=True)
    assert extras.checkins_due(agent.memory, "usr_sarra") == []      # too early
    later = datetime.now() + timedelta(days=31)
    due = extras.checkins_due(agent.memory, "usr_sarra", now=later)
    assert due and due[0]["decision_id"] == out["decision_id"]
    assert extras.checkin_answer(agent.memory, "usr_sarra", out["decision_id"], "hmm")["saved"] is False
    r = extras.checkin_answer(agent.memory, "usr_sarra", out["decision_id"], "every week")
    assert r["saved"] and r["label"] == "buy"
    rows = extras.real_labels(tmp_path)
    assert len(rows) == 1 and extras.accuracy(rows)["labels"] == 1
    assert extras.checkins_due(agent.memory, "usr_sarra", now=later) == []  # asked once only


def test_think_verdict_offers_wishlist_and_output_has_type(tmp_path):
    agent = SmartBuyAgent({**CONFIG, "real": [], "personalize": False}, memory=AgentMemory(tmp_path))
    for c in agent.clients.candidates.values():
        out = asyncio.run(agent({"user_id": c.get("user_id", "usr_demo"), "probe_image": c["id"], "price_tnd": c.get("price_tnd", 80)}))
        assert out["subcategory"] and out["colour"]
        if out["verdict"] == "think":
            assert any(a["action"] == "watch_price" for a in out["next_actions"])
            return
    pytest.skip("no THINK case in the demo data")
