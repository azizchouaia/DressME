from modules.m03_wear_log import mock
from modules.m03_wear_log.contract import WornResponse, StatsResponse

def test_worn_mock_matches_contract():
    out = WornResponse.model_validate(mock.worn({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_stats_mock_matches_contract():
    out = StatsResponse.model_validate(mock.stats({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
