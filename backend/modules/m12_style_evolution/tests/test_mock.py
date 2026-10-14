from modules.m12_style_evolution import mock
from modules.m12_style_evolution.contract import TimelineResponse

def test_timeline_mock_matches_contract():
    out = TimelineResponse.model_validate(mock.timeline({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
