from modules.m07_local_catalogue import mock
from modules.m07_local_catalogue.contract import SearchResponse

def test_search_mock_matches_contract():
    out = SearchResponse.model_validate(mock.search({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
