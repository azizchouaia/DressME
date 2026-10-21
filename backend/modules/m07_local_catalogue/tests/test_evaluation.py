"""Evaluation (evaluation/run.py): grades, metrics, understanding, and a full run on a tiny catalogue."""

import asyncio

import pytest

from modules.m07_local_catalogue.evaluation.run import (
    dcg,
    evaluate,
    human_scores,
    load_queries,
    metrics,
    parse_scores,
    relevance,
)
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue

from .test_search import ROWS, FakeEncoder

SNEAKER = {
    "subcategory": "sneakers",
    "category": "shoes",
    "price_tnd": 75.0,
    "color": "white",
    "gender": "women",
    "city": "Tunis",
    "governorate": "Tunis",
    "product_name": "Baskets blanches cuir",
}


@pytest.mark.parametrize(
    ("intent", "grade"),
    [
        ({"type": "sneakers", "color": "white"}, 2),
        ({"type": "shoes"}, 2),  # generic type = category
        ({"type": "sandals"}, 0),
        ({"type": "sneakers", "max_price": 60}, 0),  # over budget
        ({"type": "sneakers", "gender": "men"}, 0),  # other gender
        ({"type": "sneakers", "color": "black"}, 0),  # other colour: a colour asked for is strict
        ({"type": "sneakers", "color": "white", "gender": "women"}, 2),
        ({"type": "sneakers", "city": "La Marsa"}, 2),  # same governorate
        ({"type": "sneakers", "city": "Sfax"}, 1),
        ({"type": "sneakers", "name_any": ["cuir"]}, 2),
        ({"type": "sneakers", "name_any": ["daim"]}, 1),
    ],
)
def test_relevance(intent, grade):
    assert relevance(SNEAKER, intent) == grade


def test_unknown_gender_or_colour_is_partial():
    assert relevance(SNEAKER | {"gender": ""}, {"type": "sneakers", "gender": "men"}) == 1
    assert relevance(SNEAKER | {"color": ""}, {"type": "sneakers", "color": "black"}) == 1


def test_metrics():
    assert dcg([2, 0]) == pytest.approx(3.0)
    perfect = metrics([2, 2, 1], [2, 2, 1, 0])
    assert perfect["ndcg"] == pytest.approx(1.0) and perfect["mrr"] == 1.0 and perfect["p5"] == 0.4
    late = metrics([0, 1, 2], [2, 1, 0])
    assert late["mrr"] == pytest.approx(1 / 3) and late["wrong5"] == pytest.approx(1 / 3) and late["ndcg"] < 1
    assert metrics([], [2])["zero"] and metrics([0], [0, 0])["ndcg"] is None  # nothing relevant exists


def test_parse_scores_per_field():
    queries = [
        {
            "id": "q1",
            "lang": "fr",
            "query": "baskets blanches",
            "expect": {"type": "sneakers", "color": "white"},
        }
    ]
    parsed = {"q1": {"subcategory": "sneakers", "color": "black"}}
    out = parse_scores(queries, parsed)
    assert out["accuracy"]["all/type"] == 1.0 and out["accuracy"]["fr/color"] == 0.0
    assert out["accuracy"]["all/exact"] == 0.0
    assert out["misses"] == [
        {"id": "q1", "query": "baskets blanches", "field": "color", "expected": "white", "got": "black"}
    ]


def test_test_set_is_well_formed():
    queries = load_queries()
    assert len({q["id"] for q in queries}) == len(queries) >= 60
    assert {q["lang"] for q in queries} == {"fr", "en", "darija", "arabic"}
    assert all(q["expect"].get("type") for q in queries)


def test_full_run_on_tiny_catalogue():
    enc = FakeEncoder()
    emb = enc.encode_texts([f"a photo of {r['color']} sneakers" for r in ROWS])
    catalogue = Catalogue.from_records(ROWS, emb)
    queries = [
        {"id": "a", "lang": "fr", "query": "baskets blanches à Tunis max 80 TND",
         "expect": {"type": "sneakers", "color": "white", "max_price": 80, "city": "Tunis"}},
        {"id": "b", "lang": "darija", "query": "sbadri kahla",
         "expect": {"type": "sneakers", "color": "black"}},
    ]  # fmt: skip
    result = asyncio.run(evaluate(queries, catalogue, enc))
    full = result["summary"]["full"]
    # the best piece comes first; nDCG < 1 because the Tunis filter hides partial matches elsewhere
    assert full["mrr"] == 1.0 and full["zero"] == 0 and full["wrong5"] == 0
    assert result["parse"]["full"]["accuracy"]["all/exact"] == 1.0
    assert (
        result["parse"]["no_darija"]["accuracy"]["darija/exact"] == 0.0
    )  # the lexicon is what reads "sbadri"
    assert set(result["summary"]) == {
        "bm25_raw", "clip_raw", "no_clip", "visual_only", "no_darija", "no_gender", "soft_color", "full"
    }  # fmt: skip

    best = catalogue.products[result["runs"]["full"]["a"][0]]["product_id"]
    human = human_scores(queries, catalogue, result, {("a", best): 2, ("a", "p2"): 0})
    assert human["variants"]["full"]["n"] == 1 and human["pairs"] == 2
