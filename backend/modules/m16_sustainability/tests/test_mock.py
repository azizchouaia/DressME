from modules.m16_sustainability import mock
from modules.m16_sustainability.contract import ScoreResponse

def test_score_mock_matches_contract():
    out = ScoreResponse.model_validate(mock.score({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
