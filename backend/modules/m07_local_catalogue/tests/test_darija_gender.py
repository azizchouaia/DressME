"""Darija requests and gender: parsing, filter, reasons, and the photo estimate of pipeline/attributes.py."""

import asyncio

import numpy as np
import pytest

from modules.m07_local_catalogue import darija
from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.pipeline.attributes import assign, evaluate, gender_margins
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from modules.m07_local_catalogue.pipeline.parse import parse
from modules.m07_local_catalogue.taxonomy import gender_from_text

from .test_search import FakeEncoder, product


@pytest.mark.parametrize(
    ("query", "subcategory", "color"),
    [
        ("sabbat ahmar", None, "red"),  # generic "chaussures": category only
        ("sbadri kahla", "sneakers", "black"),
        ("sorya bidha", "shirt", "white"),
        ("sarwel azra9", "trousers", "blue"),
        ("صباط أحمر", None, "red"),
        ("سروال بالأسود", "trousers", "black"),  # Arabic article / preposition glued to the word
        ("mangouch dhahbi", "earrings", "gold"),
        ("سنسلة ذهبية", "necklace", "gold"),  # feminine adjective
        ("sensla dhahbia", "necklace", "gold"),
    ],
)
def test_darija_pieces_and_colours(query, subcategory, color):
    parsed = parse(query)
    assert (parsed.subcategory, parsed.color) == (subcategory, color)
    assert parsed.translated


def test_words_found_by_the_test_set():
    """Misses of the first evaluation run (evaluation/RESULTS.md): feminine and English forms."""
    assert parse("bague argentée").color == "grey"
    assert parse("leather handbag").subcategory == "bag"


def test_darija_shoes_are_the_shoes_category():
    assert parse("sabbat ahmar").category == "shoes"


def test_darija_budget_in_alf():
    parsed = parse("sbadri a9al men 100 alf")
    assert (parsed.subcategory, parsed.max_price_tnd) == ("sneakers", 100)


def test_french_request_is_not_translated():
    assert parse("baskets blanches à Tunis").translated is None
    assert darija.translate("robe rouge") is None


@pytest.mark.parametrize(
    ("query", "gender"),
    [
        ("chemise homme blanche", "men"),
        ("basket femme", "women"),
        ("cadeau pour mon mari", "men"),
        ("robba lel nsa", "women"),
        ("sorya rjel", "men"),
        ("شكارة نسائية", "women"),
        ("baskets blanches", None),
    ],
)
def test_gender_in_request(query, gender):
    assert parse(query).gender == gender


def test_gender_words_are_not_bm25_terms():
    parsed = parse("chemise homme blanche")
    assert "homme" not in parsed.terms
    assert parsed.prompt_en == "a photo of men's white shirt"


def test_gender_from_product_text():
    assert gender_from_text("Basket Femme") == "women"
    assert gender_from_text("Chemise", "https://s.tn/collections/homme/chemise") == "men"
    assert gender_from_text("Casquette unisexe") == "unisex"
    assert gender_from_text("Chemise") == ""
    assert gender_from_text("Pyjama homme et femme") == ""  # both named: unknown, not guessed
    assert gender_from_text("Women's top") == "women"  # "women" does not also match "men"


def shirt(pid, name, gender, source="text"):
    row = product(pid, name, "shirt", "top", "white", 60, "Tunis", "Tunis", "Chemises")
    return row | {"gender": gender, "gender_source": source if gender else ""}


ROWS = [
    shirt("m1", "Chemise homme blanche", "men"),
    shirt("w1", "Chemise femme blanche", "women"),
    shirt("u1", "Chemise blanche", ""),
    shirt("m2", "Chemise blanche col mao", "men", source="photo"),
]


@pytest.fixture
def agent():
    enc = FakeEncoder()
    emb = enc.encode_texts(["a photo of white shirt"] * len(ROWS))
    return LocalShopAgent(catalogue=Catalogue.from_records(ROWS, emb), encoder=enc)


def search(agent, **payload):
    return asyncio.run(agent(payload))


def test_men_request_drops_women_pieces_keeps_unknown_lower(agent):
    out = search(agent, query="chemise homme blanche")
    ids = [r["product_id"] for r in out["results"]]
    assert "w1" not in ids
    assert set(ids) == {"m1", "m2", "u1"} and ids[-1] == "u1"  # unknown gender ranked last
    reasons = {r["product_id"]: r["reasons"] for r in out["results"]}
    assert "Modèle homme" in reasons["m1"]
    assert "Modèle homme (estimé d'après la photo)" in reasons["m2"]
    assert "Genre non précisé par la boutique" in reasons["u1"]
    assert out["parsed"]["gender"] == "men"
    assert {r["product_id"]: r["gender"] for r in out["results"]}["u1"] is None


def test_explicit_gender_field_wins(agent):
    ids = [r["product_id"] for r in search(agent, query="chemise blanche", gender="women")["results"]]
    assert "w1" in ids and "m1" not in ids and "m2" not in ids


def test_no_gender_asked_keeps_everything(agent):
    assert len(search(agent, query="chemise blanche")["results"]) == 4


# --- gender from the photo (pipeline/attributes.py) ---------------------------------------------


def photo_rows():
    def row(pid, name):
        return {
            "product_id": pid,
            "product_name": name,
            "product_url": f"https://s.tn/{pid}",
            "subcategory": "shirt",
        }

    return [row("a", "Chemise femme"), row("b", "Chemise homme"), row("c", "Chemise"), row("d", "Chemise")]


def test_photo_margin_sign_and_threshold():
    w, m = np.eye(2, dtype=np.float32)
    prompts = {("women", "shirt"): w, ("men", "shirt"): m}
    vectors = {"a": w, "b": m, "c": 0.9 * m + 0.1 * w, "d": 0.5 * w + 0.5 * m}
    margins = gender_margins(photo_rows(), vectors, prompts)
    assert margins["a"] > 0 > margins["b"] and margins["d"] == pytest.approx(0)

    rows = photo_rows()
    counts = assign(rows, margins, threshold=1.5)
    by_id = {r["product_id"]: (r["gender"], r["gender_source"]) for r in rows}
    assert by_id["a"] == ("women", "text") and by_id["b"] == ("men", "text")  # text always wins
    assert by_id["c"] == ("men", "photo")
    assert by_id["d"] == ("", "")  # too close to call: unknown, not guessed
    assert counts["photo", "men"] == 1 and counts["none", "unknown"] == 1


def test_evaluation_on_written_genders():
    rows = photo_rows()
    for r in rows:
        r["gender"] = gender_from_text(r["product_name"])
        r["gender_source"] = "text" if r["gender"] else ""
    margins = {"a": 5.0, "b": 0.4, "c": 9.0}  # "b" is wrong (leans women) but below margin 1
    by_margin = {e["margin"]: e for e in evaluate(rows, margins, [0.0, 1.0])}
    assert by_margin[0.0]["labelled"] == 2
    assert by_margin[0.0]["accuracy"] == 0.5 and by_margin[1.0]["accuracy"] == 1.0
    assert by_margin[1.0]["coverage"] == 0.5
