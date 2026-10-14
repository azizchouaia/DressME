from modules.m07_local_catalogue import mock
from modules.m07_local_catalogue.contract import LocalShopOutput


def test_search_mock_matches_contract():
    out = LocalShopOutput.model_validate(mock.search({"query": "baskets blanches à Tunis 80 TND"}))
    assert out.results[0].price_tnd == 69.3
