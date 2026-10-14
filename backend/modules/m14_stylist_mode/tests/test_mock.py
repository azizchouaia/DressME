from modules.m14_stylist_mode import mock
from modules.m14_stylist_mode.contract import ClientsResponse

def test_clients_mock_matches_contract():
    out = ClientsResponse.model_validate(mock.clients({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
