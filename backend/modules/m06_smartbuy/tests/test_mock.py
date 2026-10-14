from modules.m06_smartbuy import mock
from modules.m06_smartbuy.contract import VerdictResponse

def test_verdict_mock_matches_contract():
    out = VerdictResponse.model_validate(mock.verdict({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
