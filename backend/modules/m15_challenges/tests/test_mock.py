from modules.m15_challenges import mock
from modules.m15_challenges.contract import ChallengesResponse

def test_challenges_mock_matches_contract():
    out = ChallengesResponse.model_validate(mock.challenges({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
