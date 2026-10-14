from modules.m18_size_fit import mock
from modules.m18_size_fit.contract import AdviseResponse

def test_advise_mock_matches_contract():
    out = AdviseResponse.model_validate(mock.advise({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
