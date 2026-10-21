"""End-to-end search on a tiny catalogue with a fake encoder (no torch, no network, no model download)."""

import asyncio
import hashlib

import numpy as np
import pytest

from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from modules.m07_local_catalogue.pipeline.parse import parse
from shared.base_agent import AgentError


class FakeEncoder:
    """Bag-of-words vectors: 'a photo of white sneakers' is close to a product embedded the same way."""

    def encode_texts(self, texts):
        out = np.zeros((len(texts), 512), np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % 512] += 1
        return out / np.linalg.norm(out, axis=1, keepdims=True)


def product(pid, name, sub, cat, color, price, city, gov, label, available="true"):
    return {
        "product_id": pid,
        "shop_name": f"Shop {pid}",
        "shop_url": f"https://{pid}.tn",
        "product_name": name,
        "category": cat,
        "subcategory": sub,
        "label_fr": label,
        "color": color,
        "color_fr": "",
        "color_hex": "",
        "size": "38, 39",
        "size_type": "numeric",
        "price_tnd": str(price),
        "currency": "TND",
        "city": city,
        "governorate": gov,
        "available": available,
        "origin_type": "local_brand",
        "image_url": f"https://{pid}.tn/i.jpg",
        "image_path": f"images/{pid}.jpg",
        "product_url": f"https://{pid}.tn/p",
        "last_checked": "2026-10-14",
    }


ROWS = [
    product("p1", "Baskets blanches cuir", "sneakers", "shoes", "white", 75, "Tunis", "Tunis", "Baskets"),
    product("p2", "Baskets noires", "sneakers", "shoes", "black", 70, "La Marsa", "Tunis", "Baskets"),
    product("p3", "Baskets blanches premium", "sneakers", "shoes", "white", 140, "Tunis", "Tunis", "Baskets"),
    product("p4", "Baskets blanches", "sneakers", "shoes", "white", 60, "Sfax", "Sfax", "Baskets"),
    product("p5", "Chemise en lin blanche", "shirt", "top", "white", 79, "Tunis", "Tunis", "Chemises"),
    product(
        "p6",
        "Basket blanche",
        "sneakers",
        "shoes",
        "white",
        65,
        "Tunis",
        "Tunis",
        "Baskets",
        available="false",
    ),
    product("p7", "Baskets", "sneakers", "shoes", "", 55, "", "", "Baskets"),
]
EN = {"sneakers": "sneakers", "shirt": "shirt"}


@pytest.fixture
def agent():
    enc = FakeEncoder()
    emb = enc.encode_texts([f"a photo of {r['color']} {EN[r['subcategory']]}" for r in ROWS])
    return LocalShopAgent(catalogue=Catalogue.from_records(ROWS, emb), encoder=enc)


def search(agent, **payload):
    return asyncio.run(agent(payload))


def test_parse_example_request():
    parsed = parse("baskets blanches à Tunis pour un budget de 80 TND")
    assert (parsed.subcategory, parsed.color, parsed.city, parsed.max_price_tnd) == (
        "sneakers",
        "white",
        "Tunis",
        80,
    )
    assert parsed.prompt_en == "a photo of white sneakers"


def test_example_white_sneakers_in_tunis_under_80(agent):
    out = search(agent, query="baskets blanches à Tunis pour un budget de 80 TND")
    ids = [r["product_id"] for r in out["results"]]
    # p2 black (a colour asked for is strict), p3 too expensive, p4 in Sfax, p5 not sneakers,
    # p6 out of stock, p7 colour and shop city unknown
    assert ids == ["p1"]
    top = out["results"][0]
    assert top["shop"] == "Shop p1" and top["area"] == "Tunis" and top["price_tnd"] == 75
    assert 0 <= top["match"] <= 1
    assert "Boutique à Tunis" in top["reasons"]


def test_governorate_matches_la_marsa(agent):
    out = search(agent, query="baskets noires à Tunis")
    assert out["results"][0]["product_id"] == "p2"
    assert "Boutique à La Marsa (près de Tunis)" in out["results"][0]["reasons"]


def test_city_relaxed_when_nothing_there(agent):
    out = search(agent, query="chemise en lin blanche", city="Sfax")
    assert out["note"] and [r["product_id"] for r in out["results"]] == ["p5"]


def test_explicit_fields_override_text(agent):
    out = search(agent, query="baskets", max_price_tnd=58, include_unavailable=True)
    assert [r["product_id"] for r in out["results"]] == ["p7"]


def test_colour_asked_is_strict_and_relaxed_only_when_it_exists_nowhere(agent):
    out = search(agent, query="baskets noires")
    assert [r["color"] for r in out["results"]] == ["black"] and out["note"] is None
    out = search(agent, query="baskets rouges")  # no red sneakers at all: say it, show the others
    assert out["results"] and "Aucun article de couleur rouge parmi les baskets" in out["note"]
    out = search(agent, query="baskets noires à Sfax")  # black exists, but not in Sfax: keep the colour
    assert [r["product_id"] for r in out["results"]] == ["p2"] and "Rien trouvé à Sfax" in out["note"]


def test_pages_follow_each_other_without_repeats(agent):
    everything = [r["product_id"] for r in search(agent, query="baskets", k=10)["results"]]
    page1 = search(agent, query="baskets", k=2)
    page2 = search(agent, query="baskets", k=2, offset=2)
    page3 = search(agent, query="baskets", k=2, offset=4)
    shown = [r["product_id"] for p in (page1, page2, page3) for r in p["results"]]
    assert sorted(shown) == sorted(everything) and len(set(shown)) == len(shown)
    assert page2["total_matches"] == page1["total_matches"] == len(everything)
    assert search(agent, query="baskets", k=2, offset=50)["results"] == []


def test_missing_colour_is_not_guessed(agent):
    out = search(agent, query="baskets blanches", max_price_tnd=58)
    result = out["results"][0]
    assert result["color"] is None
    assert any("non précisée" in reason for reason in result["reasons"])


def test_style_vector_and_image_embedding(agent):
    vec = FakeEncoder().encode_texts(["a photo of black sneakers"])[0].tolist()
    out = search(agent, subcategory="sneakers", image_embedding=vec, k=1)
    assert out["results"][0]["product_id"] == "p2"
    black_style = FakeEncoder().encode_texts(["black"])[0].tolist()  # a user who wears black
    out = search(agent, subcategory="sneakers", style_vector=black_style, k=1)
    assert out["results"][0]["product_id"] == "p2"
    with pytest.raises(AgentError):
        search(agent, subcategory="sneakers", style_vector=[1.0, 2.0])


def test_nothing_found(agent):
    out = search(agent, query="robe", max_price_tnd=10)
    assert out["results"] == [] and out["total_matches"] == 0


def test_explicit_fields_only_still_use_the_visual_search(agent):
    out = search(agent, subcategory="sneakers", color="black")
    assert out["parsed"]["prompt_en"] == "a photo of black sneakers"
    assert out["results"][0]["product_id"] == "p2"


def test_typo_is_corrected_towards_known_words():
    parsed = parse(
        "chemize doré",
        vocabulary={"chemise"}
        | __import__("modules.m07_local_catalogue.pipeline.parse", fromlist=["KEYWORDS"]).KEYWORDS,
    )
    assert parsed.corrected == "chemise doré"  # only the misspelt word changes
    assert parsed.subcategory == "shirt"
    assert parse("colier doré").subcategory == "necklace"  # frequent shop spelling: a rule word itself


def test_typo_also_written_by_a_shop_is_still_corrected():
    # a shop writes "Chemize": the catalogue vocabulary contains the typo, the keyword still wins
    parsed = parse("chemize blanche", vocabulary={"chemize"})
    assert parsed.subcategory == "shirt" and parsed.color == "white"
    assert parse("robes noires", vocabulary={"robe"}).corrected is None  # understood words stay


def test_jewelry_types_are_separate():
    assert parse("bracelet").subcategory == "bracelet"
    assert parse("bague argent").subcategory == "ring"
    assert parse("costume homme").subcategory == "suit"
    assert parse("pantalon de costume").subcategory == "trousers"


def test_unknown_words_do_not_return_unrelated_pieces(agent):
    out = search(agent, query="zorglub")
    assert out["results"] == [] and "zorglub" in out["note"]
    out = search(agent, query="cuir")  # not a type, but present in a product name: only that product
    assert [r["product_id"] for r in out["results"]] == ["p1"]


def test_sold_out_pieces_shown_when_nothing_in_stock(agent):
    # Only p6 is a white sneaker at most 65 TND in Tunis, and it is sold out.
    out = search(agent, query="baskets blanches à Tunis", max_price_tnd=65, min_price_tnd=62)
    assert [r["product_id"] for r in out["results"]] == ["p6"]
    assert out["results"][0]["available"] is False and "rupture" in out["note"]


def test_city_filter_shows_the_matching_city_and_says_when_the_colour_is_missing(agent):
    out = search(agent, query="baskets noires à Tunis")
    assert out["results"][0]["area"] == "La Marsa"  # the shop's city inside the Tunis governorate
    out = search(agent, query="chemise noire", city="Tunis")  # p5 is the only shirt, and it is white
    assert [r["product_id"] for r in out["results"]] == ["p5"]
    assert "Aucun article de couleur noir parmi les chemises à Tunis" in out["note"]
