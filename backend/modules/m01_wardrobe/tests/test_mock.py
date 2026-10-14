from modules.m01_wardrobe import mock
from modules.m01_wardrobe.contract import ClassifyResponse, SimilarResponse, ItemsResponse

def test_classify_mock_matches_contract():
    out = ClassifyResponse.model_validate(mock.classify({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_similar_mock_matches_contract():
    out = SimilarResponse.model_validate(mock.similar({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_items_mock_matches_contract():
    out = ItemsResponse.model_validate(mock.items({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
