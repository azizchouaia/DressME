from modules.m05_style_profile import mock
from modules.m05_style_profile.contract import ProfileResponse, FeedbackResponse, GapsResponse

def test_profile_mock_matches_contract():
    out = ProfileResponse.model_validate(mock.profile({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_feedback_mock_matches_contract():
    out = FeedbackResponse.model_validate(mock.feedback({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_gaps_mock_matches_contract():
    out = GapsResponse.model_validate(mock.gaps({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
