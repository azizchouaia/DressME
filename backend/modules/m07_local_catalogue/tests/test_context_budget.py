"""BO6 ideas 8 and 9: Tunisian occasions and seasons in a request, and the usual budget learned in memory."""

import asyncio

import pytest

from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from modules.m07_local_catalogue.pipeline.parse import parse
from shared.base_agent import AgentError

from .test_search import FakeEncoder, product

ROWS = [
    product("d1", "Robe à bretelles en lin", "dress", "dress", "white", 120, "Tunis", "Tunis", "Robes"),
    product("d2", "Robe velours manches longues", "dress", "dress", "black", 130, "Tunis", "Tunis", "Robes"),
    product("d3", "Robe midi", "dress", "dress", "red", 110, "Tunis", "Tunis", "Robes"),
    product("t1", "Jebba brodée", "traditional", "traditional", "white", 250, "Tunis", "Tunis", "Tenues"),
    product("s1", "Costume 2 pièces", "suit", "dress", "navy", 300, "Sfax", "Sfax", "Costumes"),
    product("w1", "Maillot une pièce", "swimwear", "dress", "blue", 60, "Sousse", "Sousse", "Maillots"),
    product("a1", "Sandales plates", "sandals", "shoes", "beige", 45, "Sousse", "Sousse", "Sandales"),
    product("b1", "Bottes en cuir", "boots", "shoes", "black", 180, "Tunis", "Tunis", "Bottes"),
    product("k1", "Baskets blanches", "sneakers", "shoes", "white", 60, "Tunis", "Tunis", "Baskets"),
    product("k2", "Baskets cuir", "sneakers", "shoes", "white", 95, "Tunis", "Tunis", "Baskets"),
    product("k3", "Baskets premium", "sneakers", "shoes", "white", 190, "Tunis", "Tunis", "Baskets"),
    product("k4", "Baskets montantes", "sneakers", "shoes", "white", 150, "Tunis", "Tunis", "Baskets"),
]


@pytest.fixture
def agent():
    enc = FakeEncoder()
    # same picture for every piece of a type: only the season / budget parts can change the order
    emb = enc.encode_texts([f"a photo of {r['subcategory']}" for r in ROWS])
    return LocalShopAgent(catalogue=Catalogue.from_records(ROWS, emb), encoder=enc)


def call(agent, **payload):
    return asyncio.run(agent(payload))


# ---- idea 8: occasions and seasons
@pytest.mark.parametrize(
    ("query", "occasion"),
    [
        ("tenue pour un mariage", "mariage"),
        ("n7eb lebsa l 3ers o5ti", "mariage"),
        ("عندي عرس في سوسة", "mariage"),
        ("an outfit for a job interview", "entretien"),
        ("tenue pour les soirées de ramadan", "ramadan"),
        ("robe de soirée pour un mariage", "mariage"),  # the first occasion of the lexicon wins
        ("tenue pour la fête de l'aïd", "aïd"),
    ],
)
def test_occasion_is_read_in_every_language(query, occasion):
    assert parse(query).occasion == occasion


def test_season_said_or_implied_by_the_beach():
    assert parse("robe d'été").season == "summer"
    assert parse("pull pour l'hiver").season == "winter"
    assert parse("7ajti b sorya fi sif").season == "summer"
    assert parse("tenue pour la plage").season == "summer"  # the beach is a summer occasion
    assert parse("robe noire").season is None


def test_occasion_words_are_not_keywords():
    parsed = parse("tenue pour un mariage")
    assert parsed.terms == [] and parsed.occasion_pieces[0] == "dress"
    assert parse("robe pour un mariage").occasion_pieces == []  # a piece is named: the type decides


def test_an_occasion_alone_searches_the_pieces_worn_for_it(agent):
    out = call(agent, query="tenue pour un mariage", k=10)
    wedding = {"dress", "set", "suit", "jumpsuit", "traditional", "heels"}
    assert {r["subcategory"] for r in out["results"]} <= wedding
    assert out["total_matches"] == 5 and out["question"] is None  # understood: no "which piece?" question
    assert out["note"].startswith("Pour un mariage : robes, ensembles, costumes")
    assert "Pour un mariage" in out["results"][0]["reasons"]


def test_summer_and_winter_reorder_the_same_dresses(agent):
    summer = call(agent, query="robe d'été", k=3)
    winter = call(agent, query="robe pour l'hiver", k=3)
    assert summer["results"][0]["product_id"] == "d1" and summer["results"][-1]["product_id"] == "d2"
    assert winter["results"][0]["product_id"] == "d2" and winter["results"][-1]["product_id"] == "d1"
    assert "Pièce pour l'été" in summer["results"][0]["reasons"]
    assert summer["total_matches"] == winter["total_matches"] == 3  # a season never hides a piece


def test_beach_in_english_and_the_explicit_fields(agent):
    out = call(agent, query="beach", language="en", k=5)
    assert {r["subcategory"] for r in out["results"]} == {"swimwear", "sandals"}
    assert out["note"].startswith("For the beach:")
    assert out["results"][0]["reasons"][:2] == ["For the beach", "A piece for summer"]
    field = call(agent, occasion="wedding", k=10)  # orchestrator field, any word of the lexicon
    assert field["parsed"]["occasion"] == "mariage"
    with pytest.raises(AgentError, match="unknown occasion"):
        call(agent, occasion="picnic on mars")


# ---- idea 9: the usual budget learned from memory
def test_usual_budget_learned_from_the_budgets_given(agent):
    call(agent, query="baskets moins de 80 dt", user_id="u1", session_id="s1")
    call(agent, query="baskets blanches max 100 dt", user_id="u1", session_id="s2")
    out = call(agent, query="baskets", user_id="u1", session_id="s3", k=4)
    assert out["parsed"]["usual_budget_tnd"] == 90.0 and out["parsed"]["max_price_tnd"] is None
    assert out["memory_notes"] == [
        "Ton budget habituel pour les baskets : ~90 TND (appris de 2 de tes recherches ou achats) ; "
        "les pièces dans ce budget passent en premier."
    ]
    assert [r["price_tnd"] for r in out["results"]][:2] == [60, 95]  # within (or just over) 90 TND first
    assert out["total_matches"] == 4  # a usual budget never hides a piece
    assert "Dans ton budget habituel (≤ 90 TND)" in out["results"][0]["reasons"]
    other = call(agent, query="baskets", user_id="u2", session_id="s1", k=4)
    assert other["parsed"]["usual_budget_tnd"] is None  # memory is per user


def test_a_budget_said_wins_and_one_budget_is_not_enough(agent):
    call(agent, query="baskets moins de 80 dt", user_id="u3", session_id="s1")
    alone = call(agent, query="baskets", user_id="u3", session_id="s2")
    assert alone["parsed"]["usual_budget_tnd"] is None  # min_samples: 2
    call(agent, query="baskets max 100 dt", user_id="u3", session_id="s3")
    said = call(agent, query="baskets moins de 200 dt", user_id="u3", session_id="s4")
    assert said["parsed"]["usual_budget_tnd"] is None and said["parsed"]["max_price_tnd"] == 200


def test_purchases_count_and_the_category_is_the_fallback(agent):
    first = call(agent, query="sandales", user_id="u4", session_id="s1")
    agent.memory.feedback("u4", first["decision_id"], useful=True, bought_product_id="a1")  # 45 TND
    call(agent, query="bottes max 150 dt", user_id="u4", session_id="s2")
    out = call(agent, query="chaussures", user_id="u4", session_id="s3")  # category shoes: 45 and 150
    assert out["parsed"]["usual_budget_tnd"] == 97.5
    assert "chaussures" in out["memory_notes"][0]
    agent.memory.forget("u4")
    again = call(agent, query="chaussures", user_id="u4", session_id="s4")
    assert again["parsed"]["usual_budget_tnd"] is None
