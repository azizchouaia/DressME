from shared.agent_card import build_mock_agent

from . import mock
from .identity import CARD

Agent = build_mock_agent(
    CARD, lambda inp: mock.profile({"user_id": inp.user_id, "payload": {"message": inp.message, **inp.payload}})
)
