from modules.m08_llm_layer import mock
from modules.m08_llm_layer.contract import ParseResponse, ExplainResponse

def test_parse_mock_matches_contract():
    out = ParseResponse.model_validate(mock.parse({"user_id": "u1", "payload": {}}))
    assert out.mocked is True

def test_explain_mock_matches_contract():
    out = ExplainResponse.model_validate(mock.explain({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
