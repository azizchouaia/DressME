"""TestClient on every M5 endpoint: M1 mocked (demo wardrobe usr_demo, 13 items), M5 in memory."""

import json

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m05_style_profile import m01_client, service, styles
from modules.m05_style_profile.config import load_reference_looks
from modules.m05_style_profile.repository import get_store
from modules.m05_style_profile.router import router

DEMO = "usr_demo"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def swipe(cards, like=lambda card: card["kind"] == "look") -> list[dict]:
    return [
        {"log_id": c["log_id"], "reaction": "like" if like(c) else "reject", "source": "onboarding"}
        for c in cards
    ]


def onboard(client, user=DEMO, like=lambda card: card["kind"] == "look"):
    """A new user's whole onboarding: the swipe cards straight away, every card answered (no question)."""
    cards = client.get("/m05/onboarding/swipe-cards", params={"user_id": user}).json()["cards"]
    r = client.post("/m05/feedback", json={"user_id": user, "events": swipe(cards, like)})
    assert r.status_code == 200, r.text
    p = client.get(f"/m05/profile/{user}").json()
    assert p["onboarded"]
    return p


def test_router_is_mounted_by_the_gateway():
    from api.main import app

    paths = {r.path for r in app.routes}
    assert {
        "/m05/onboarding/swipe-cards",
        "/m05/choose",
        "/m05/feedback",
        "/m05/profile/{user_id}",
        "/m05/explain/{user_id}",
        "/m05/preferences",
        "/m05/styles/recompute",
        "/m05/profile",
        "/m05/gaps",
        "/m05/ui",
    } <= paths
    gone = {"start", "analyze", "form", "confirm", "analyze-later", "looks"}  # no question before the swipes
    assert not {f"/m05/onboarding/{p}" for p in gone} & paths


# ---------- onboarding: swipes only ----------


def test_swipe_cards_are_the_first_screen(client):
    assert client.get(f"/m05/profile/{DEMO}").status_code == 404
    r = client.get("/m05/onboarding/swipe-cards", params={"user_id": DEMO}).json()
    cards = r["cards"]
    assert len(cards) == 10 and r["n_candidates"] > 10 and "reference_looks" in r["candidates_source"]
    looks = {c["look_id"] for c in cards if c["kind"] == "look"}
    assert len(looks) >= 9  # at least one look per family
    assert [c["rank"] for c in cards] == list(range(10)) and cards[0]["score"] >= cards[-1]["score"]
    assert all(c["images"] and c["top_styles"] and not c["explore"] for c in cards)
    # an empty profile: nothing asked, nothing guessed
    p = client.get(f"/m05/profile/{DEMO}").json()
    assert not p["onboarded"] and p["answers"] == {} and p["style_mix"] == {} and p["taste_vector"] is None
    e = client.get(f"/m05/explain/{DEMO}").json()
    assert e["positive"] == [] and e["negative"] == []
    assert client.get("/m05/onboarding/swipe-cards", params={"user_id": ""}).status_code == 422


async def test_onboarding_swipes_build_the_profile(client):
    cards = client.get("/m05/onboarding/swipe-cards", params={"user_id": DEMO}).json()["cards"]
    liked = [c for c in cards if c["kind"] == "look"][:2]
    events = swipe(cards, lambda c: c in liked)
    out = client.post("/m05/feedback", json={"user_id": DEMO, "events": events[:-1]}).json()
    assert out["applied"] == 9
    assert client.get(f"/m05/profile/{DEMO}").json()["onboarded"] is False  # one card left
    client.post("/m05/feedback", json={"user_id": DEMO, "events": events[-1:]})
    p = client.get(f"/m05/profile/{DEMO}").json()
    assert p["onboarded"] and p["n_feedback"] == 10 and p["answers"] == {}

    # Rocchio: taste = normalise(mean(liked) - 0.3 * mean(rejected)); the style mix is the taste's
    space = await styles.get_space()
    taste = _unit(np.mean([await _emb(c) for c in liked], 0) - 0.3 * np.mean(
        [await _emb(c) for c in cards if c not in liked], 0
    ))
    np.testing.assert_allclose(p["taste_vector"], taste, atol=1e-6)
    assert p["style_mix"] == pytest.approx(space.as_dict(space.mix(taste)), abs=1e-3)
    assert abs(sum(p["style_mix"].values()) - 1) < 1e-2
    assert await get_store().get_bandit(DEMO) is None  # the bandit is kept but not used


def _unit(v):
    return v / np.linalg.norm(v)


async def _emb(card) -> np.ndarray:
    if card["kind"] == "look":
        looks = await service.reference_looks()
        return next(np.asarray(lk.embedding) for lk in looks if lk.id == card["look_id"])
    return _unit(np.mean(list((await m01_client.embeddings(DEMO, card["item_ids"])).values()), 0))


def test_swipe_cards_again_replace_the_open_batch(client):
    first = client.get("/m05/onboarding/swipe-cards", params={"user_id": DEMO}).json()["cards"]
    client.post("/m05/feedback", json={"user_id": DEMO, "events": swipe(first[:3])})
    second = client.get("/m05/onboarding/swipe-cards", params={"user_id": DEMO}).json()["cards"]
    client.post("/m05/feedback", json={"user_id": DEMO, "events": swipe(second)})
    p = client.get(f"/m05/profile/{DEMO}").json()
    assert p["onboarded"] and p["n_feedback"] == 13
    out = client.post("/m05/feedback", json={"user_id": DEMO, "events": swipe(first[3:4])}).json()
    assert out["applied"] == 1  # a late answer to the old batch is still learnt


def test_new_user_with_an_empty_wardrobe_swipes_reference_looks(client):
    r = client.get("/m05/onboarding/swipe-cards", params={"user_id": "new_user"}).json()
    assert r["candidates_source"] == "reference_looks" and len(r["cards"]) == 10
    assert {c["kind"] for c in r["cards"]} == {"look"}
    p = onboard(client, "new_user")
    assert len(p["taste_vector"]) == 512 and p["top_styles"]


# ---------- daily loop ----------


def test_choose_from_m2_mock_and_feedback(client):
    onboard(client)
    r = client.post(
        "/m05/choose", json={"user_id": DEMO, "context": {"temp_c": 18, "occasion": "work", "weekend": False}}
    )
    assert r.status_code == 200
    out = r.json()
    assert out["candidates_source"] == "m02_mock" and 0 < len(out["cards"]) <= 10
    assert out["n_candidates"] >= len(out["cards"])
    card = out["cards"][0]
    assert card["kind"] == "outfit" and card["item_ids"] and card["images"][0].startswith("/m01/")
    assert card["context"]["occasion"] == "work"
    fb = client.post(
        "/m05/feedback",
        json={
            "user_id": DEMO,
            "events": [
                {"log_id": card["log_id"], "reaction": "heart"},
                {"log_id": card["log_id"], "reaction": "reject"},  # same card twice
                {"outfit_id": out["cards"][1]["outfit_id"], "reaction": "ignored"},  # by outfit id
            ],
        },
    ).json()
    assert [x["status"] for x in fb["results"]] == ["applied", "duplicate", "applied"]
    assert fb["results"][0]["reward"] == 1.0 and fb["results"][2]["reward"] == 0.2
    p = client.get(f"/m05/profile/{DEMO}").json()
    assert p["n_feedback"] == 10 + 2  # the onboarding swipes + this batch


def test_choose_with_given_candidates_and_no_exploration(client):
    onboard(client)
    cands = [
        {"item_ids": ["itm_demo_shirt_navy", "itm_demo_chino_beige"]},
        {"outfit_id": "o2", "item_ids": ["itm_demo_dress_red", "unknown_item"]},
        {"item_ids": ["unknown_only"]},
    ]
    r = client.post(
        "/m05/choose", json={"user_id": DEMO, "candidates": cands, "explore": False, "k": 5}
    ).json()
    assert r["candidates_source"] == "request" and r["n_candidates"] == 2
    assert {c["outfit_id"] for c in r["cards"]} >= {"o2"}
    assert next(c for c in r["cards"] if c["outfit_id"] == "o2")["item_ids"] == ["itm_demo_dress_red"]
    again = client.post("/m05/choose", json={"user_id": DEMO, "candidates": cands, "explore": False}).json()
    assert [c["outfit_id"] for c in again["cards"]] == [c["outfit_id"] for c in r["cards"]]  # mean model


def test_choose_validation_and_empty(client):
    assert (
        client.post("/m05/choose", json={"user_id": DEMO, "context": {"occasion": "beach"}}).status_code
        == 422
    )
    assert client.post("/m05/choose", json={"user_id": DEMO, "context": {"temp_c": 99}}).status_code == 422
    assert client.post("/m05/choose", json={"user_id": DEMO, "k": 0}).status_code == 422
    r = client.post("/m05/choose", json={"user_id": "empty_wardrobe"}).json()  # works without a profile
    assert r["cards"] == [] and r["n_candidates"] == 0


def test_choose_is_fast(client):
    onboard(client)
    cands = [
        {"item_ids": ["itm_demo_shirt_navy", "itm_demo_chino_beige", "itm_demo_loafers"]},
        {"item_ids": ["itm_demo_sweatshirt_grey", "itm_demo_jeans_blue", "itm_demo_sneakers_white"]},
        {"item_ids": ["itm_demo_dress_red", "itm_demo_sneakers_white"]},
        {"item_ids": ["itm_demo_shirt_navy_2", "itm_demo_jeans_blue", "itm_demo_jacket_leather"]},
    ] * 5
    client.post("/m05/choose", json={"user_id": DEMO, "candidates": cands})  # warm the caches
    times = [
        client.post("/m05/choose", json={"user_id": DEMO, "candidates": cands}).json()["elapsed_ms"]
        for _ in range(5)
    ]
    assert sorted(times)[2] < 50


def test_feedback_sources_and_validation(client):
    onboard(client)
    worn = {
        "item_ids": ["itm_demo_jeans_blue", "itm_demo_sweatshirt_grey"],
        "reaction": "worn",
        "source": "worn",
        "context": {"temp_c": 9, "occasion": "casual"},
    }
    chat = {"look_id": "look_party", "reaction": "like", "source": "chat", "context": {"occasion": "event"}}
    r = client.post("/m05/feedback", json={"user_id": DEMO, "events": [worn, chat]}).json()
    assert [(x["status"], x["weight"]) for x in r["results"]] == [("applied", 1.0), ("applied", 0.5)]
    bad = [
        {"reaction": "like"},
        {"log_id": "x", "reaction": "meh"},
        {"log_id": "x", "reaction": "like", "source": "email"},
    ]
    for ev in bad:
        assert client.post("/m05/feedback", json={"user_id": DEMO, "events": [ev]}).status_code == 422
    assert client.post("/m05/feedback", json={"user_id": DEMO, "events": []}).status_code == 422
    r = client.post(
        "/m05/feedback", json={"user_id": DEMO, "events": [{"log_id": "lg_unknown", "reaction": "like"}]}
    )
    assert r.status_code == 422
    r = client.post(
        "/m05/feedback", json={"user_id": DEMO, "events": [{"item_ids": ["nope"], "reaction": "like"}]}
    )
    assert r.status_code == 422


async def test_reactions_move_the_taste_vector(client):
    onboard(client)
    cards = client.post("/m05/choose", json={"user_id": DEMO, "explore": False}).json()["cards"]

    def react(card, reaction) -> np.ndarray:
        event = {"log_id": card["log_id"], "reaction": reaction}
        client.post("/m05/feedback", json={"user_id": DEMO, "events": [event]})
        return np.array(client.get(f"/m05/profile/{DEMO}").json()["taste_vector"])

    t0 = np.array(client.get(f"/m05/profile/{DEMO}").json()["taste_vector"])
    np.testing.assert_allclose(react(cards[0], "ignored"), t0)  # neither liked nor rejected
    e = await _emb(cards[1])
    t1 = react(cards[1], "reject")
    assert float(t1 @ e) < float(t0 @ e)  # moves away
    e = await _emb(cards[2])
    t2 = react(cards[2], "heart")
    assert float(t2 @ e) > float(t1 @ e) and abs(np.linalg.norm(t2) - 1) < 1e-6  # moves closer


def test_choose_ranks_by_taste_with_discovery_cards(client, cfg):
    onboard(client)
    r = client.post("/m05/choose", json={"user_id": DEMO}).json()
    cards = r["cards"]
    assert len(cards) == 10 and r["n_candidates"] > 10
    explore = [c for c in cards if c["explore"]]
    close = [c["score"] for c in cards if not c["explore"]]
    assert len(explore) == cfg.rocchio.explore_cards and close == sorted(close, reverse=True)
    assert all(c["score"] < min(close) for c in explore)  # picked away from the taste
    ranked = client.post("/m05/choose", json={"user_id": DEMO, "explore": False}).json()["cards"]
    assert not any(c["explore"] for c in ranked)
    assert [c["score"] for c in ranked] == sorted((c["score"] for c in ranked), reverse=True)


@pytest.mark.parametrize("ranking", ["rocchio", "bandit"])
def test_learns_from_repeated_swipes(client, cfg, monkeypatch, ranking):
    """Liking every dress card and rejecting the rest makes dresses rank first, with either ranking."""
    monkeypatch.setattr(cfg, "ranking", ranking)
    onboard(client)
    dress = {"item_ids": ["itm_demo_dress_red", "itm_demo_sneakers_white"]}
    other = [
        {"item_ids": ["itm_demo_sweatshirt_grey", "itm_demo_jeans_blue", "itm_demo_sneakers_white"]},
        {"item_ids": ["itm_demo_shirt_navy", "itm_demo_chino_beige", "itm_demo_loafers"]},
    ]
    for _ in range(15):
        cards = client.post("/m05/choose", json={"user_id": DEMO, "candidates": [dress, *other]}).json()[
            "cards"
        ]
        client.post(
            "/m05/feedback",
            json={
                "user_id": DEMO,
                "events": [
                    {
                        "log_id": c["log_id"],
                        "reaction": "heart" if "itm_demo_dress_red" in c["item_ids"] else "reject",
                    }
                    for c in cards
                ],
            },
        )
    ranked = client.post(
        "/m05/choose", json={"user_id": DEMO, "candidates": [*other, dress], "explore": False}
    ).json()["cards"]
    assert "itm_demo_dress_red" in ranked[0]["item_ids"]


# ---------- profile / explain / styles ----------


def test_profile_for_other_bos(client):
    assert client.get("/m05/profile/nobody").status_code == 404
    onboard(client)
    p = client.get(f"/m05/profile/{DEMO}").json()
    assert {"style_mix", "families", "top_families", "top_styles", "taste_vector", "n_feedback"} <= set(p)
    assert not any(k.startswith("_") for k in p["answers"])
    env = client.post("/m05/profile", json={"user_id": DEMO}).json()
    assert env["mocked"] is False and env["result"]["onboarded"] and "taste_vector" not in env["result"]
    assert client.post("/m05/profile", json={"user_id": "nobody"}).json()["result"]["onboarded"] is False
    assert client.delete(f"/m05/profile/{DEMO}").json()["deleted"]
    assert client.get(f"/m05/profile/{DEMO}").status_code == 404
    assert client.delete(f"/m05/profile/{DEMO}").status_code == 404


def test_explain(client):
    assert client.get("/m05/explain/nobody").status_code == 404
    onboard(client)
    e = client.get(f"/m05/explain/{DEMO}").json()
    assert e["n_feedback"] == 10 and e["positive"] and e["negative"]
    assert all(r["feature"].startswith("style:") and r["label"].startswith("likes") for r in e["positive"])
    assert all(r["weight"] < 0 and r["label"].startswith("avoids") for r in e["negative"])
    card = client.post("/m05/choose", json={"user_id": DEMO}).json()["cards"][0]
    e = client.get(f"/m05/explain/{DEMO}", params={"log_id": card["log_id"], "k": 3}).json()
    assert e["card"][0]["feature"] == "taste_sim"
    assert e["card"][0]["weight"] == pytest.approx(card["score"], abs=1e-3)
    assert 0 < len(e["card"]) <= 3
    assert client.get(f"/m05/explain/{DEMO}", params={"log_id": "lg_nope"}).status_code == 404


def test_explain_bandit(client, bandit_mode):
    onboard(client)
    e = client.get(f"/m05/explain/{DEMO}").json()
    assert e["n_feedback"] == 10 and e["positive"] and all(r["weight"] <= 0 for r in e["negative"])  # rounded
    assert all(r["label"] and r["uncertainty"] > 0 for r in [*e["positive"], *e["negative"]])
    card = client.post("/m05/choose", json={"user_id": DEMO}).json()["cards"][0]
    e = client.get(f"/m05/explain/{DEMO}", params={"log_id": card["log_id"], "k": 3}).json()
    assert 0 < len(e["card"]) <= 3
    assert client.get(f"/m05/explain/{DEMO}", params={"log_id": "lg_nope"}).status_code == 404


def test_styles_and_look_pictures(client):
    s = client.get("/m05/styles").json()
    assert len(s["styles"]) == 12 and len(s["families"]) == 9 and s["dim"] == 90
    r = client.get("/m05/ui/looks/look_party.svg")
    assert (
        r.status_code == 200
        and r.headers["content-type"].startswith("image/svg+xml")
        and "Night out" in r.text
    )
    assert client.get("/m05/ui/looks/nope.svg").status_code == 404
    ui = client.get("/m05/ui")
    assert ui.status_code == 200 and "M5" in ui.text
    assert client.get("/m05/ui/app.js").status_code == 200
    assert client.post("/m05/gaps", json={"user_id": DEMO}).json()["mocked"] is True


async def test_reference_looks_use_their_local_photos(client, cfg, monkeypatch, tmp_path):
    data = json.loads((service.MODULE_DIR / "reference_looks.json").read_text(encoding="utf-8"))
    by_id = {lk["id"]: lk for lk in data["looks"]}
    by_id["look_classic"] |= {"image_url": "/m05/ui/looks/photos/look_classic.png", "vector_source": "image"}
    path = tmp_path / "looks.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cfg, "reference_looks_file", str(path))
    sent = []
    embed_images = m01_client.embed_images

    async def spy(images, user_id="m05_system"):
        sent.extend(images)
        return await embed_images(images, user_id)

    monkeypatch.setattr(m01_client, "embed_images", spy)
    looks = {lk.id: lk for lk in await service.reference_looks(reseed=True)}
    assert len(sent) == 1 and sent[0].startswith("data:image/png;base64,")  # M1 cannot read M5's own paths
    assert looks["look_classic"].image_url == "/m05/ui/looks/photos/look_classic.png"
    r = client.get(looks["look_classic"].image_url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert looks["look_party"].image_url == "/m05/ui/looks/look_party.svg"  # the drawing


def test_every_look_is_drawn_with_its_outfit(client):
    for d in load_reference_looks():
        assert d.art, d.id
        r = client.get(f"/m05/ui/looks/{d.id}.svg")
        assert r.status_code == 200 and r.text.startswith("<svg") and d.title in r.text
    party = client.get("/m05/ui/looks/look_party.svg").text
    assert "look_party-dress" in party  # the sequin pattern of its dress


async def test_a_missing_look_photo_falls_back_to_the_placeholder(cfg, monkeypatch, tmp_path):
    data = json.loads((service.MODULE_DIR / "reference_looks.json").read_text(encoding="utf-8"))
    data["looks"][0] |= {"image_url": "/m05/ui/looks/photos/nope.png", "vector_source": "image"}
    path = tmp_path / "looks.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cfg, "reference_looks_file", str(path))
    look = (await service.reference_looks(reseed=True))[0]
    assert look.image_url == f"/m05/ui/looks/{look.id}.svg"  # shown: the placeholder
    text_vec = (await m01_client.embed_texts([data["looks"][0]["description"]]))[0]
    expected = text_vec / np.linalg.norm(text_vec)  # the vector of its description
    np.testing.assert_allclose(look.embedding, expected, atol=1e-6)


def test_style_list_change_recomputes_and_resizes(client, cfg, monkeypatch, tmp_path, bandit_mode):
    onboard(client)
    client.post("/m05/preferences", json={"user_id": DEMO, "more": ["classic"]})
    old = client.post("/m05/choose", json={"user_id": DEMO}).json()["cards"][0]
    first = client.post("/m05/styles/recompute", json={"user_id": DEMO}).json()
    assert first["n_styles"] == 12 and first["dim"] == 90 and first["recomputed"] == 13

    data = json.loads((service.MODULE_DIR / "styles.json").read_text(encoding="utf-8"))
    data["styles"] = [
        s for s in data["styles"] if s["id"] in {"classic", "casual", "bohemian", "party", "sport"}
    ]
    small = tmp_path / "styles_small.json"
    small.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cfg, "styles_file", str(small))
    r = client.post("/m05/styles/recompute", json={"user_id": DEMO}).json()
    assert r["n_styles"] == 5 and r["dim"] == 1 + 9 + 30 + 1 and r["dropped"] == 13 and r["recomputed"] == 13
    assert r["styles_version"] != first["styles_version"]

    fb = client.post(
        "/m05/feedback", json={"user_id": DEMO, "events": [{"log_id": old["log_id"], "reaction": "like"}]}
    ).json()
    assert fb["results"][0]["status"] == "skipped"  # old features: logged, not learned
    cards = client.post("/m05/choose", json={"user_id": DEMO}).json()["cards"]
    assert cards and all(
        s["style"] in {"classic", "casual", "bohemian", "party", "sport"} for s in cards[0]["top_styles"]
    )
    fb = client.post(
        "/m05/feedback",
        json={"user_id": DEMO, "events": [{"log_id": cards[0]["log_id"], "reaction": "like"}]},
    ).json()
    assert fb["results"][0]["status"] == "applied"
    e = client.get(f"/m05/explain/{DEMO}").json()
    assert "style:classic" in {x["feature"] for x in e["positive"]}  # prior rebuilt from the wishes
