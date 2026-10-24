"""mock.py answers have the real contract shapes, so the other BOs can code against M7 offline."""

from modules.m07_local_catalogue import mock
from modules.m07_local_catalogue.contract import LocalPiecesOutput, LocalShopOutput, OutfitsOutput


def test_search_mock_matches_contract():
    out = LocalShopOutput.model_validate(mock.search({"query": "baskets blanches à Tunis 80 TND"}))
    assert out.results[0].price_tnd == 69.3


def test_outfits_and_local_pieces_mocks_match_contract():
    outfits = OutfitsOutput.model_validate(mock.outfits({"product_id": "prd_x", "user_id": "u"}))
    assert outfits.product_id == "prd_x" and outfits.sources == {"m1": "mock", "m2": "mock"}
    pieces = LocalPiecesOutput.model_validate(mock.local_pieces({"user_id": "u", "item_ids": ["itm_jean01"]}))
    assert pieces.suggestions[0].slot == "shoes"
