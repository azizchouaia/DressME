from modules.m10_share_cards import mock
from modules.m10_share_cards.contract import CardResponse


def test_card_mock_matches_contract():
    out = CardResponse.model_validate(mock.card({"user_id": "u1", "payload": {}}))
    assert out.mocked is True
