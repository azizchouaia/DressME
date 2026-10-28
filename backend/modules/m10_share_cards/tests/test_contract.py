import json
from pathlib import Path

from modules.m10_share_cards.agent import ShareAgent
from modules.m10_share_cards.contract import ShareCardInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    ShareCardInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = ShareAgent()
    assert agent.name == "share"
    assert agent.description
