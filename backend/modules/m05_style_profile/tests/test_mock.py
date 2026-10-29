"""The week-1 envelope kept for the BO8 orchestrator (agent.py calls mock.profile)."""

from modules.m05_style_profile import mock
from modules.m05_style_profile.contract import GapsResponse, ProfileEnvelope


def test_profile_mock_matches_the_envelope():
    out = ProfileEnvelope.model_validate(mock.profile({"user_id": "u1", "payload": {}}))
    assert out.mocked is True and out.result["user_id"] == "u1"


def test_gaps_mock_matches_the_envelope():
    out = GapsResponse.model_validate(mock.gaps({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
