"""End-to-end API tests for the BO7 modules (M10 share cards, M15 challenges)."""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("PIL")

from api.main import app  # noqa: E402

client = TestClient(app)

OUTFIT = {
    "user_id": "usr_api",
    "kind": "outfit",
    "title": "Linen day",
    "items": [
        {"item_id": "a", "category": "top", "label": "Linen shirt", "color_hex": "#E3CFAE"},
        {"item_id": "b", "category": "bottom", "label": "Chinos", "color_hex": "#D9C3A0"},
    ],
}


def test_share_card_flow():
    r = client.post("/m10/cards", json=OUTFIT)
    assert r.status_code == 200, r.text
    card = r.json()
    img = client.get(card["image_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert client.get(f"/m10/s/{card['short_code']}").status_code == 200
    assert (
        client.post(f"/m10/s/{card['short_code']}/signup", json={"new_user_id": "friend"}).status_code == 204
    )
    m = client.get("/m10/metrics", params={"user_id": "usr_api"}).json()
    assert m["cards"] == 1 and m["opens"] == 1 and m["signups"] == 1


def test_share_errors():
    assert client.post("/m10/cards", json={"user_id": "u"}).status_code == 400
    assert client.get("/m10/s/zzzzzzz").status_code == 404
    assert client.post("/m10/cards", json={"user_id": "u", "kind": "nope"}).status_code == 422


def test_challenge_flow():
    user = "usr_api_ch"
    lst = client.get("/m15/challenges", params={"user_id": user}).json()
    assert len(lst) >= 5 and "feasibility" in lst[0]

    assert client.post("/m15/challenges/ch_7x7/join", json={"user_id": user}).json()["next_day"] == 1
    ok = client.post(
        "/m15/challenges/ch_7x7/entries", json={"user_id": user, "item_ids": ["itm_t1", "itm_b1", "itm_s1"]}
    ).json()
    assert ok["valid"] and ok["post"]["card_image_url"]
    bad = client.post(
        "/m15/challenges/ch_7x7/entries", json={"user_id": user, "item_ids": ["itm_t2", "itm_b1", "itm_s2"]}
    ).json()
    assert not bad["valid"] and bad["violations"]

    prog = client.get("/m15/challenges/ch_7x7/progress", params={"user_id": user}).json()
    assert prog["days_logged"] == 2 and prog["valid_days"] == 1

    post_id = ok["post"]["post_id"]
    assert client.post(f"/m15/challenges/posts/{post_id}/like", json={"user_id": "fan"}).json()["likes"] == 1
    board = client.get("/m15/challenges/ch_7x7/leaderboard").json()
    assert any(r["user_id"] == user for r in board)
    assert any(p["post_id"] == post_id for p in client.get("/m15/challenges/posts/all").json())


def test_challenge_errors():
    assert client.get("/m15/challenges/nope", params={"user_id": "u"}).status_code == 404
    r = client.post("/m15/challenges/ch_mono/entries", json={"user_id": "not_joined", "item_ids": ["itm_t1"]})
    assert r.status_code == 400


def test_landing_page_channels_and_create_challenge():
    card = client.post("/m10/cards", json=OUTFIT).json()
    assert set(card["channel_links"]) >= {"whatsapp", "instagram", "copy"}
    page = client.get(f"/m10/s/{card['short_code']}/page", params={"ch": "whatsapp"})
    assert page.status_code == 200 and 'property="og:image"' in page.text
    client.post(f"/m10/s/{card['short_code']}/signup", json={"new_user_id": "friend_wa"})
    m = client.get("/m10/metrics", params={"user_id": OUTFIT["user_id"]}).json()
    assert any(r["channel"] == "whatsapp" and r["signups"] >= 1 for r in m["channels"])

    body = {
        "user_id": "brand_x",
        "title": "Navy days",
        "description": "One navy piece a day.",
        "duration_days": 3,
        "rules": [{"type": "color_theme", "params": {"colors": ["navy"], "mode": "any"}}],
    }
    r = client.post("/m15/challenges/create", json=body)
    assert r.status_code == 201 and r.json()["created_by"] == "brand_x"
    bad = {**body, "title": "Gold days", "rules": [{"type": "color_theme", "params": {"colors": ["gold"]}}]}
    assert client.post("/m15/challenges/create", json=bad).status_code == 400
