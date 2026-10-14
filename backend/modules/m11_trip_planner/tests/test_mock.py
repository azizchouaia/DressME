from modules.m11_trip_planner import mock
from modules.m11_trip_planner.contract import PlanResponse

def test_plan_mock_matches_contract():
    out = PlanResponse.model_validate(mock.plan({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
