from modules.m17_capsule import mock
from modules.m17_capsule.contract import CapsuleResponse

def test_capsule_mock_matches_contract():
    out = CapsuleResponse.model_validate(mock.capsule({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
