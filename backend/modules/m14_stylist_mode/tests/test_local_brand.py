"""BO6 Backup 2 (loyalty codes of boutique accounts) and Backup 5 (local brand challenges through M15).

M15 (BO7) is simulated until `m15` is listed in config.yaml `real`; the real path is tested with a fake M15.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m14_stylist_mode import clients, mock
from modules.m14_stylist_mode import router as m14_router
from modules.m14_stylist_mode.contract import LocalChallenge, LoyaltyCode
from modules.m14_stylist_mode.paths import CONFIG
from modules.m14_stylist_mode.simulate import pros


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(m14_router.router)
    asyncio.run(pros.seed())
    return TestClient(app)


def boutique(api, shop="Manuella"):
    return next(p for p in api.get("/m14/pro", params={"type": "boutique"}).json() if p["shop"] == shop)


# ---- Backup 2: loyalty codes
def test_demo_boutiques_have_demo_codes_and_m7_can_read_them(api):
    codes = api.get("/m14/loyalty").json()
    assert codes and all(c["code"].endswith("-DEMO10") and c["discount_pct"] == 10 for c in codes)
    assert [c["shop"] for c in api.get("/m14/loyalty", params={"shop": "Manuella"}).json()] == ["Manuella"]


def test_a_boutique_sets_and_removes_its_code(api):
    pro = boutique(api)
    body = {
        "loyalty": {
            "code": "MANUELLA15",
            "discount_pct": 15,
            "until": "2099-12-31",
            "conditions": "dès 100 TND",
        }
    }
    assert api.patch(f"/m14/pro/{pro['pro_id']}", json=body).json()["loyalty"]["code"] == "MANUELLA15"
    assert api.get("/m14/loyalty", params={"shop": "Manuella"}).json()[0]["discount_pct"] == 15
    assert api.delete(f"/m14/pro/{pro['pro_id']}/loyalty").json()["loyalty"] is None
    assert api.get("/m14/loyalty", params={"shop": "Manuella"}).json() == []
    expired = {"loyalty": {"code": "OLD10", "discount_pct": 10, "until": "2020-01-01"}}
    api.patch(f"/m14/pro/{pro['pro_id']}", json=expired)
    assert api.get("/m14/loyalty", params={"shop": "Manuella"}).json() == []  # past its last day


def test_only_a_boutique_has_a_code_and_codes_are_checked(api):
    stylist = api.get("/m14/pro", params={"type": "stylist"}).json()[0]
    code = {"loyalty": {"code": "STYLE10", "discount_pct": 10}}
    assert api.patch(f"/m14/pro/{stylist['pro_id']}", json=code).status_code == 422
    bad = {"loyalty": {"code": "lower case", "discount_pct": 10}}
    assert api.patch(f"/m14/pro/{boutique(api)['pro_id']}", json=bad).status_code == 422


# ---- Backup 5: a boutique sponsors a local brand challenge (M15)
def test_challenge_is_simulated_until_m15_is_merged(api):
    pro = boutique(api)
    out = api.post("/m14/challenges", json={"pro_id": pro["pro_id"]}).json()
    assert out["challenge_id"].startswith("sim_chl_") and out["sources"] == {"m15": "mock", "m7": "real"}
    assert out["title"] == "7 jours avec Manuella" and out["sponsor"] == "Manuella"
    assert out["rules"] == [
        {"type": "local_brand", "params": {"min": 1}},
        {"type": "no_repeat", "params": {}},
    ]
    assert out["pieces"] and {p["shop"] for p in out["pieces"]} == {"Manuella"}
    listed = api.get("/m14/challenges", params={"pro_id": pro["pro_id"]}).json()
    assert [c["challenge_id"] for c in listed] == [out["challenge_id"]]
    stylist = api.get("/m14/pro", params={"type": "stylist"}).json()[0]
    assert api.post("/m14/challenges", json={"pro_id": stylist["pro_id"]}).status_code == 422


def test_challenge_published_on_the_real_m15(api, monkeypatch):
    monkeypatch.setitem(CONFIG, "real", ["m7", "m15"])
    sent = []

    def fake_post(path, body):
        sent.append((path, body))
        return {**body, "challenge_id": "chl_42", "participants": 3}

    monkeypatch.setattr(clients, "_post", fake_post)
    pro = boutique(api)
    body = {
        "pro_id": pro["pro_id"],
        "duration_days": 10,
        "min_local_pieces": 2,
        "no_repeat": False,
        "language": "en",
    }
    out = api.post("/m14/challenges", json=body).json()
    assert (out["challenge_id"], out["participants"], out["sources"]["m15"]) == ("chl_42", 3, "real")
    path, sent_body = sent[0]
    assert path == "/m15/challenges/create" and sent_body["user_id"] == pro["pro_id"]
    assert sent_body["rules"] == [{"type": "local_brand", "params": {"min": 2}}]
    assert sent_body["title"] == "10 days with Manuella" and sent_body["duration_days"] == 10


def test_mocks_have_the_contract_shapes():
    assert LoyaltyCode.model_validate(mock.loyalty_codes()[0]).code == "MANUELLA-DEMO10"
    assert LocalChallenge.model_validate(mock.local_challenge()).sponsor == "Manuella"


def test_one_active_challenge_per_shop_until_it_is_ended(api):
    pro = boutique(api)
    first = api.post("/m14/challenges", json={"pro_id": pro["pro_id"]}).json()
    assert first["status"] == "active" and first["ends_on"] == str(
        datetime.now(UTC).date() + timedelta(days=6)
    )
    again = api.post("/m14/challenges", json={"pro_id": pro["pro_id"]})
    assert again.status_code == 409 and first["challenge_id"] in again.json()["detail"]
    ended = api.post(f"/m14/challenges/{first['challenge_id']}/end").json()
    assert ended["status"] == "ended" and ended["ended_at"]
    second = api.post("/m14/challenges", json={"pro_id": pro["pro_id"]}).json()
    assert [c["status"] for c in api.get("/m14/challenges", params={"pro_id": pro["pro_id"]}).json()] == [
        "active",
        "ended",
    ]
    assert second["challenge_id"] != first["challenge_id"]
    one = api.get(f"/m14/challenges/{first['challenge_id']}").json()  # what BO7's screen reads
    assert one["status"] == "ended" and one["pieces"] and one["pieces"][0]["product_url"]
    assert api.get("/m14/challenges/nope").status_code == 404
    assert api.post("/m14/challenges/nope/end").status_code == 404


def test_a_challenge_past_its_last_day_is_ended(api):
    from modules.m14_stylist_mode import store

    pro = boutique(api)
    c = api.post("/m14/challenges", json={"pro_id": pro["pro_id"], "duration_days": 3}).json()
    record = store.challenges.get(c["challenge_id"])
    store.challenges.put(c["challenge_id"], {**record, "ends_on": "2020-01-03"})
    assert api.get("/m14/challenges", params={"pro_id": pro["pro_id"]}).json()[0]["status"] == "ended"
    assert api.post("/m14/challenges", json={"pro_id": pro["pro_id"]}).status_code == 200
