"""BO6 ideas 3 and 10: a local piece with the user's wardrobe (M1) and M2's compatibility / outfits.

Until M1 and M2 are merged, clients.py answers with a simulation and `sources` says "mock"; once they are
listed in config.yaml `real`, the same code calls them (here faked) and `sources` says "real".
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import clients, service
from modules.m07_local_catalogue import router as m07_router
from modules.m07_local_catalogue.contract import OutfitsInput
from shared.base_agent import AgentError

from .test_search import agent  # noqa: F401  (fixture: tiny catalogue, fake encoder)


def search(a, **payload):
    return asyncio.run(a(payload))


def outfits(a, **payload):
    return asyncio.run(a.outfits(OutfitsInput(**payload))).model_dump()


# ---- idea 10: "why this local piece" says what it goes with in the wardrobe
def test_top_results_say_which_wardrobe_pieces_they_go_with(agent):  # noqa: F811
    out = search(agent, query="chemise en lin blanche", user_id="u1", k=1)
    top = out["results"][0]
    assert top["wardrobe_matches"][:2] == ["jean (bleu)", "baskets (blanc)"]
    assert "Va avec ta garde-robe : jean (bleu), baskets (blanc), veste (bleu marine)" in top["reasons"]
    assert out["sources"] == {"m1": "mock", "m2": "mock"}  # simulation until M1 / M2 are merged
    english = search(agent, query="chemise en lin blanche", user_id="u1", k=1, language="en")
    assert english["results"][0]["reasons"][-1].startswith(
        "Goes with your wardrobe: blue jeans, white sneakers"
    )


def test_anonymous_searches_have_no_wardrobe(agent):  # noqa: F811
    out = search(agent, query="chemise en lin blanche", k=1)
    assert out["results"][0]["wardrobe_matches"] == [] and out["sources"] == {}


# ---- idea 3: outfits from the wardrobe around a local piece
def test_outfits_around_a_local_shirt(agent):  # noqa: F811
    out = outfits(agent, user_id="u1", product_id="p5", n=2)
    assert out["piece"] == "Chemise en lin blanche · Shop p5 · 79 TND"
    first = out["outfits"][0]["pieces"]
    assert [(p["source"], p["label"]) for p in first] == [
        ("shop", "Chemise en lin blanche"),
        ("wardrobe", "jean (bleu)"),
        ("wardrobe", "baskets (blanc)"),
    ]
    assert out["why"] == [
        "Marque tunisienne : Shop p5 à Tunis",
        "79 TND",
        "Va avec ta garde-robe : jean (bleu), baskets (blanc), veste (bleu marine)",
    ]
    assert out["sources"] == {"m1": "mock", "m2": "mock"}


def test_outfits_errors_and_occasion(agent):  # noqa: F811
    with pytest.raises(AgentError, match="unknown product_id"):
        outfits(agent, user_id="u1", product_id="nope")
    with pytest.raises(AgentError, match="unknown occasion"):
        outfits(agent, user_id="u1", product_id="p5", occasion="picnic on mars")
    assert outfits(agent, user_id="u1", product_id="p5", occasion="wedding")["outfits"]


# ---- after the integration: the same code calls M1 and M2 for real
def test_real_m1_m2_are_used_once_listed_and_a_failure_falls_back(agent, monkeypatch):  # noqa: F811
    monkeypatch.setitem(clients.CONFIG, "real", ["m1", "m2"])
    wardrobe = [
        {"item_id": "w9", "category": "bottom", "subcategory": "trousers", "colors": [{"name": "black"}]}
    ]
    calls = []

    def fake_post(path, body):
        calls.append(path)
        if path == "/m01/items":
            return {"items": wardrobe}
        if path == "/m02/score":
            return {"result": {"outfits": [{"items": ["p5", "w9"], "score": 0.91}]}}
        if path == "/m02/complete":
            assert body["payload"]["pinned_item_ids"] == ["p5"]
            assert body["payload"]["context"]["occasion"] == "work"  # entretien -> M2's work context
            return {
                "result": {"outfits": [{"items": ["p5", "w9"], "score": 0.88, "reasons": ["M2: good pair"]}]}
            }
        raise AssertionError(path)

    monkeypatch.setattr(clients, "_post", fake_post)
    out = outfits(agent, user_id="u1", product_id="p5", occasion="entretien")
    assert out["sources"] == {"m1": "real", "m2": "real"}
    assert out["outfits"][0]["score"] == 0.88 and out["outfits"][0]["reasons"] == ["M2: good pair"]
    assert out["goes_with"] == ["pantalon (noir)"]
    assert calls == ["/m01/items", "/m02/score", "/m02/complete"]

    def down(path, body):
        raise ConnectionError("M2 not running")

    monkeypatch.setattr(clients, "_post", down)
    assert outfits(agent, user_id="u1", product_id="p5")["sources"] == {"m1": "mock", "m2": "mock"}


def test_outfits_endpoint(agent, monkeypatch):  # noqa: F811
    monkeypatch.setattr(service, "knowledge_base_ready", lambda: True)
    monkeypatch.setattr(service, "_agent", agent)
    app = FastAPI()
    app.include_router(m07_router.router)
    api = TestClient(app)
    ok = api.post("/m07/outfits", json={"user_id": "u1", "product_id": "p5", "language": "en"})
    assert ok.status_code == 200 and ok.json()["why"][0] == "Tunisian brand: Shop p5 in Tunis"
    assert api.post("/m07/outfits", json={"user_id": "u1", "product_id": "nope"}).status_code == 422


# ---- Selected 4: Tunisian pieces inside an outfit of the day (BO1)
def local_pieces(a, **payload):
    from modules.m07_local_catalogue.contract import LocalPiecesInput

    return asyncio.run(a.local_pieces(LocalPiecesInput(**payload))).model_dump()


def test_local_pieces_complete_then_replace_a_piece_of_the_outfit(agent):  # noqa: F811
    out = local_pieces(agent, user_id="u1", item_ids=["itm_jean01", "itm_chem01"])
    assert out["outfit"] == ["jean (bleu)", "chemise (blanc)"]
    first, second = out["suggestions"]
    assert (first["action"], first["slot"], first["product"]["subcategory"]) == (
        "complete",
        "shoes",
        "sneakers",
    )
    assert first["reasons"][:2] == ["Complète ta tenue : chaussures", "Avec : jean (bleu), chemise (blanc)"]
    assert (second["action"], second["replaces"], second["product"]["product_id"]) == (
        "replace",
        "chemise (blanc)",
        "p5",
    )
    assert second["reasons"][1] == "Avec : jean (bleu)"  # scored without the piece it replaces
    assert out["sources"] == {"m1": "mock", "m2": "mock"}


def test_local_pieces_follow_the_budget_and_the_errors(agent):  # noqa: F811
    cheap = local_pieces(agent, user_id="u1", item_ids=["itm_jean01", "itm_chem01"], max_price_tnd=62, n=1)
    assert [s["product"]["price_tnd"] for s in cheap["suggestions"]] == [60.0]
    with pytest.raises(AgentError, match="none of item_ids"):
        local_pieces(agent, user_id="u1", item_ids=["not_mine"])


def test_local_pieces_with_real_m2(agent, monkeypatch):  # noqa: F811
    monkeypatch.setitem(clients.CONFIG, "real", ["m2"])  # M1 still simulated, M2 real (faked)

    def fake_post(path, body):
        assert path == "/m02/score"
        outfits = body["payload"]["outfits"]
        return {"result": {"outfits": [{"items": o, "score": 0.9 if "p4" in o else 0.55} for o in outfits]}}

    monkeypatch.setattr(clients, "_post", fake_post)
    out = local_pieces(agent, user_id="u1", item_ids=["itm_jean01", "itm_chem01"], n=1)
    assert out["sources"] == {"m1": "mock", "m2": "real"}
    assert out["suggestions"][0]["product"]["product_id"] == "p4" and out["suggestions"][0]["score"] == 0.9


def test_a_one_piece_outfit_is_completed_never_replaced(agent):  # noqa: F811
    out = local_pieces(agent, user_id="u1", item_ids=["itm_robe01"])
    assert out["outfit"] == ["robe (rouge)"]
    assert [s["action"] for s in out["suggestions"]] == ["complete"]  # sneakers with the red dress
