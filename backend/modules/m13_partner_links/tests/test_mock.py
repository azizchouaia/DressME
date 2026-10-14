from modules.m13_partner_links import mock
from modules.m13_partner_links.contract import LinksResponse

def test_links_mock_matches_contract():
    out = LinksResponse.model_validate(mock.links({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
