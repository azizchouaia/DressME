from modules.m02_recommendation import mock
from modules.m02_recommendation.contract import RecommendResponse

def test_recommend_mock_matches_contract():
    out = RecommendResponse.model_validate(mock.recommend({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
