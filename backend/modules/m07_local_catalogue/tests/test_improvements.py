"""Improvements after the BO6 ideas: dressy occasions, photo gender / season, freshness, try-on, Arabic."""

import asyncio

import numpy as np
import pytest

from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.paths import CONFIG
from modules.m07_local_catalogue.pipeline.attributes import (
    assign,
    assign_season,
    evaluate_season,
    type_priors,
)
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from modules.m07_local_catalogue.taxonomy import gender_from_text, piece_name

from .test_search import FakeEncoder, product

ROWS = [
    product("h1", "Escarpins dorés", "heels", "shoes", "gold", 120, "Tunis", "Tunis", "Escarpins"),
    product("s1", "Baskets blanches", "sneakers", "shoes", "white", 90, "Tunis", "Tunis", "Baskets"),
    product("j1", "Veste sport zippée", "jacket", "outerwear", "black", 80, "Tunis", "Tunis", "Vestes"),
    product("j2", "Veste tailleur", "jacket", "outerwear", "black", 150, "Tunis", "Tunis", "Vestes"),
    product("c1", "Chemise blanche", "shirt", "top", "white", 70, "Tunis", "Tunis", "Chemises"),
    {**product("t1", "Top fluide", "tshirt", "top", "red", 40, "Tunis", "Tunis", "Tops"), "season": "summer",
     "season_source": "photo"},
]  # fmt: skip


@pytest.fixture
def agent():
    enc = FakeEncoder()
    emb = enc.encode_texts([f"a photo of {r['subcategory']}" for r in ROWS])
    return LocalShopAgent(catalogue=Catalogue.from_records(ROWS, emb), encoder=enc)


def call(a, **payload):
    return asyncio.run(a(payload))


# ---- a dressy occasion leaves casual pieces out (the "sports jacket at a wedding")
def test_shoes_for_a_wedding_are_not_sneakers_unless_asked(agent):
    shoes = call(agent, query="chaussures pour un mariage")
    assert [r["product_id"] for r in shoes["results"]] == ["h1"]
    asked = call(agent, query="baskets pour un mariage")  # the user named sneakers: they stay
    assert [r["product_id"] for r in asked["results"]] == ["s1"]
    jackets = call(agent, query="veste pour un mariage")
    assert [r["product_id"] for r in jackets["results"]] == ["j2"]
    beach = call(agent, query="veste pour la plage")  # the beach is not dressy
    assert {r["product_id"] for r in beach["results"]} == {"j1", "j2"}


# ---- gender words, the type rule and the season from the photo (attributes.py)
def test_garments_that_say_the_gender():
    assert gender_from_text("Abaya satinée noire") == "women"
    assert gender_from_text("Qamis zein léger") == "men"
    assert gender_from_text("Caftan brodé") == "women"


def test_a_photo_gender_against_its_type_is_dropped():
    rows = [{"subcategory": "heels", "gender": "women", "gender_source": "text"} for _ in range(20)]
    rows += [{"subcategory": "heels", "gender": "men", "gender_source": "text"}]
    assert type_priors(rows, 0.95) == {"heels": "women"}  # 20 / 21 = 95.2 %
    photo = [
        {"product_id": "x", "product_name": "Escarpin", "product_url": "", "subcategory": "heels"},
        {"product_id": "y", "product_name": "Chemise", "product_url": "", "subcategory": "shirt"},
    ]
    counts = assign(photo, {"x": -5.0, "y": -5.0}, 2.0, {"heels": "women"})
    assert (photo[0]["gender"], photo[1]["gender"]) == ("", "men")  # men's heels: dropped
    assert counts["prior", "dropped"] == 1


def test_season_from_the_name_first_then_the_photo():
    rows = [
        {"product_id": "a", "product_name": "Robe en lin", "category": "dress"},
        {"product_id": "b", "product_name": "Pull en laine", "category": "top"},
        {"product_id": "c", "product_name": "Robe midi", "category": "dress"},
        {"product_id": "d", "product_name": "Robe longue", "category": "dress"},
    ]
    margins = {"a": 3.0, "b": -1.0, "c": -2.5, "d": 0.5}
    evaluation = evaluate_season(rows, margins, [0.0, 2.0])
    assert evaluation[0]["accuracy"] == 1.0 and evaluation[1]["coverage"] == 0.5
    assign_season(rows, margins, 2.0)
    assert [(r["season"], r["season_source"]) for r in rows] == [
        ("summer", "text"),
        ("winter", "text"),
        ("winter", "photo"),
        ("", ""),  # margin 0.5: not sure enough
    ]


def test_the_photo_season_counts_when_the_name_says_nothing(agent):
    out = call(agent, query="top pour l'été", k=1)
    assert out["results"][0]["product_id"] == "t1" and "Pièce pour l'été" in out["results"][0]["reasons"]


# ---- freshness of the catalogue, try-on, Arabic
def test_old_prices_are_said(agent, monkeypatch):
    monkeypatch.setitem(CONFIG, "stale_after_days", 0)
    out = call(agent, query="chemise blanche")
    assert out["note"] == "Prix et stocks relevés le 2026-10-14 : à vérifier sur le site de la boutique."


def test_try_on_is_a_next_action_for_the_avatar(agent):
    acts = {a["action"]: a for a in call(agent, query="chemise blanche")["next_actions"]}
    assert acts["try_on"]["tool"] == "tryon"
    assert acts["try_on"]["args"]["image_path"] == "images/c1.jpg"


def test_arabic_reasons_and_notes(agent):
    out = call(agent, query="chemise blanche", language="ar")
    assert out["results"][0]["reasons"][:2] == ["قمصان", "اللون: أبيض"]
    wedding = call(agent, query="veste pour un mariage", language="ar")
    assert "لـعرس" in wedding["results"][0]["reasons"]
    assert piece_name("shirt", "white", "ar") == "قميص أبيض"
    assert np.isclose(len(out["results"]), 1)


@pytest.mark.parametrize(
    ("query", "subcategory", "color"),
    [("قميص أبيض", "shirt", "white"), ("فستان أحمر", "dress", "red"), ("تنورة سوداء", "skirt", "black")],
)
def test_arabic_piece_words(query, subcategory, color):
    from modules.m07_local_catalogue.pipeline.parse import parse

    parsed = parse(query)
    assert (parsed.subcategory, parsed.color) == (subcategory, color)
