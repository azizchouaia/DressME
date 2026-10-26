"""BO7 social features (feed, poll, give-away, tags, board, recap, trip, timeline, recreate, stylist, follow),
with the other teams' modules mocked by bo7_sharing/integrations.py."""

import base64
import io

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from api.main import app  # noqa: E402
from bo.bo7_sharing import integrations as ext  # noqa: E402
from bo.bo7_sharing import social_store  # noqa: E402

client = TestClient(app)
U, FRIEND = "usr_042", "amen"


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch):
    monkeypatch.setattr(social_store, "_store", social_store.SocialStore(":memory:"))
    # the fixture wardrobe points to s3:// photos (no MinIO in tests): draw the cards without photos
    from modules.m10_share_cards.pipeline import render

    load = render.load_image
    monkeypatch.setattr(
        render,
        "load_image",
        lambda src, *a, **k: None if str(src).startswith("s3://") else load(src, *a, **k),
    )


def _ids(category: str, user: str = U) -> list[str]:
    return [g.item_id for g in ext.wardrobe(user) if g.category.value == category]


def test_board_is_completed_by_m2_mock_and_published_in_the_feed():
    r = client.post("/bo7/social/board", json={"user_id": U, "item_ids": [_ids("top")[0]], "publish": True})
    assert r.status_code == 200, r.text
    body = r.json()
    cats = {g.category.value for g in ext.wardrobe(U) if g.item_id in body["item_ids"]}
    assert {"top", "bottom", "shoes"} <= cats  # the missing slots were filled
    assert body["sources"]["complete"] == "mock" and body["card"]["image_url"]
    feed = client.get(f"/bo7/social/feed?user_id={U}").json()
    assert feed[0]["kind"] == "board" and feed[0]["user_name"] == "Omar"


def test_owner_answer_is_used_when_the_team_ships_its_module(monkeypatch):
    real = {"added": [], "missing": []}
    monkeypatch.setattr(
        ext, "_owner", lambda module, fn, req: real if module == "m02_recommendation" else None
    )
    body = client.post("/bo7/social/board", json={"user_id": U, "item_ids": [_ids("top")[0]]}).json()
    assert body["sources"]["complete"] == "M02" and body["added"] == []


def test_week1_placeholder_counts_as_not_built():
    assert ext._owner("m03_wear_log", "stats", {"user_id": U, "payload": {}}) is None  # mock says {"todo": …}


def test_poll_gets_a_verdict_and_friends_vote():
    cand = {"label": "white t-shirt", "category": "top", "color_hex": "#F1EFE9"}  # already owned → skip/think
    r = client.post("/bo7/social/polls", json={"user_id": U, "candidate": cand})
    assert r.status_code == 201, r.text
    poll = r.json()["poll"]
    assert poll["verdict"]["verdict"] in ("skip", "think") and poll["verdict"]["similar"]
    pid = poll["poll_id"]
    assert (
        client.post(f"/bo7/social/polls/{pid}/vote", json={"voter_id": U, "choice": "yes"}).status_code == 422
    )
    client.post(f"/bo7/social/polls/{pid}/vote", json={"voter_id": FRIEND, "choice": "yes"})
    v = client.post(f"/bo7/social/polls/{pid}/vote", json={"voter_id": "yasmine", "choice": "no"}).json()
    assert v["votes"] == {"yes": 1, "no": 1} and v["yes_share"] == 0.5 and v["my_vote"] == "no"
    v = client.post(f"/bo7/social/polls/{pid}/vote", json={"voter_id": "yasmine", "choice": "yes"}).json()
    assert v["votes"] == {"yes": 2, "no": 0}  # a friend can change their vote, not vote twice


def test_new_kind_of_piece_is_worth_buying():
    v = ext.smartbuy_verdict(U, {"label": "neon green skirt", "category": "bottom", "color_hex": "#39FF14"})
    assert v["verdict"] == "buy" and v["new_outfits"] > 0 and not v["similar"]


def test_giveaway_flow_suggest_post_request_give():
    sug = client.get(f"/bo7/social/giveaway/suggestions?user_id={U}").json()
    assert sug["items"] and all("reason" in p for p in sug["items"])
    assert not any(str(p.get("image", "")).startswith("/home") for p in sug["items"])  # no server paths
    item = sug["items"][0]["item_id"]
    g = client.post("/bo7/social/giveaways", json={"user_id": U, "item_id": item, "size": "M"}).json()[
        "giveaway"
    ]
    gid = g["giveaway_id"]
    assert (
        client.post(f"/bo7/social/giveaways/{gid}/give", json={"user_id": U, "to_user": FRIEND}).status_code
        == 422
    )
    client.post(f"/bo7/social/giveaways/{gid}/request", json={"user_id": FRIEND, "message": "Me please"})
    done = client.post(f"/bo7/social/giveaways/{gid}/give", json={"user_id": U, "to_user": FRIEND}).json()
    assert done["status"] == "given" and done["given_to"] == FRIEND
    again = client.post(f"/bo7/social/giveaways/{gid}/request", json={"user_id": "yasmine"})
    assert again.status_code == 422
    left = client.get(f"/bo7/social/giveaway/suggestions?user_id={U}").json()["items"]
    assert item not in {p["item_id"] for p in left}  # a piece is given once


def test_recap_uses_wear_stats():
    body = client.post("/bo7/social/recap", json={"user_id": U, "month": "2026-09"}).json()
    assert body["month"] == "2026-09" and body["sources"]["wear_log"] == "mock"
    assert body["top_items"] and body["card"]["height"] == 1920
    assert ext.wear_stats(U, "2026-09") == ext.wear_stats(U, "2026-09")  # the mock is deterministic


def test_trip_reuses_pieces_and_timeline_tells_a_story():
    t = client.post("/bo7/social/trip", json={"user_id": U, "destination": "Djerba", "days": 5}).json()
    assert len(t["plan"]) == 5 and len(t["packing"]) < 5 * 3  # fewer pieces than outfits
    tl = client.post("/bo7/social/timeline", json={"user_id": U, "months": 4}).json()
    assert len(tl["months"]) == 4 and tl["title"]


def test_feed_like_comment_moderation_and_tags():
    client.post("/bo7/social/board", json={"user_id": U, "item_ids": [_ids("top")[0]], "publish": True})
    post = client.get(f"/bo7/social/feed?user_id={FRIEND}").json()[0]
    assert (
        client.post(f"/bo7/social/posts/{post['post_id']}/like", json={"user_id": FRIEND}).json()["likes"]
        == 1
    )
    ok = client.post(
        f"/bo7/social/posts/{post['post_id']}/comments", json={"user_id": FRIEND, "text": "Love it"}
    )
    bad = client.post(
        f"/bo7/social/posts/{post['post_id']}/comments", json={"user_id": FRIEND, "text": "ugly"}
    )
    assert ok.status_code == 201 and bad.status_code == 422
    again = client.get(f"/bo7/social/feed?user_id={FRIEND}").json()[0]
    assert again["liked"] and again["comments"] == 1
    tags = client.get(
        f"/bo7/social/pieces?user_id={U}&item_ids={','.join(post['item_ids'])}&shop=false"
    ).json()
    assert [p["item_id"] for p in tags["pieces"]] == post["item_ids"]


def test_recreate_a_friends_look_with_my_pieces():
    client.post("/bo7/social/board", json={"user_id": U, "item_ids": [_ids("top")[0]], "publish": True})
    post = client.get(f"/bo7/social/feed?user_id={FRIEND}").json()[0]
    r = client.post("/bo7/social/recreate", json={"user_id": FRIEND, "post_id": post["post_id"]}).json()
    assert r["inspired_by"] == U and r["pieces"] and 0 < r["match_score"] <= 1
    assert {p["category"] for p in r["pieces"]} == {t["category"] for t in r["targets"]}


def test_recreate_from_a_photo():
    img = Image.new("RGB", (100, 200), (255, 255, 255))
    img.paste((20, 40, 160), (25, 30, 75, 100))  # blue top
    img.paste((30, 30, 30), (30, 100, 70, 176))  # black bottom
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    photo = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    r = client.post("/bo7/social/recreate", json={"user_id": U, "photo": photo, "make_card": False}).json()
    cats = [t["category"] for t in r["targets"]]
    assert "top" in cats and "bottom" in cats and r["origin"] == "photo"


def test_stylist_shares_a_look_with_a_client_only():
    items = [_ids("top")[0], _ids("bottom")[0]]
    ok = client.post(
        "/bo7/social/stylist/share",
        json={"stylist_id": "sty_amel", "client_id": U, "item_ids": items, "note": "Friday"},
    )
    assert ok.status_code == 201
    no = client.post(
        "/bo7/social/stylist/share", json={"stylist_id": "sty_amel", "client_id": FRIEND, "item_ids": items}
    )
    assert no.status_code == 403
    inbox = client.get(f"/bo7/social/inbox/{U}").json()
    assert inbox[0]["stylist_name"].startswith("Amel") and inbox[0]["note"] == "Friday"


def test_similar_profiles_and_following_feed():
    sim = client.get(f"/bo7/social/profiles/similar?user_id={U}").json()["profiles"]
    scores = [p["similarity"] for p in sim]
    assert scores == sorted(scores, reverse=True) and len(set(scores)) > 1
    client.post(
        "/bo7/social/board", json={"user_id": FRIEND, "item_ids": [_ids("top", FRIEND)[0]], "publish": True}
    )
    client.post(
        "/bo7/social/board",
        json={"user_id": "yasmine", "item_ids": [_ids("top", "yasmine")[0]], "publish": True},
    )
    client.post("/bo7/social/follow", json={"user_id": U, "target": FRIEND})
    mine = client.get(f"/bo7/social/feed?user_id={U}&scope=following").json()
    assert {p["user_id"] for p in mine} == {FRIEND}
    assert client.post("/bo7/social/follow", json={"user_id": U, "target": U}).status_code == 422


def test_integration_status_lists_every_module():
    s = client.get("/bo7/social/integrations").json()
    assert s["total"] == 8 and {r["source"] for r in s["modules"]} <= {
        "mock",
        "M1",
        "M02",
        "M03",
        "M05",
        "M06",
        "M11",
        "M12",
        "M14",
    }
