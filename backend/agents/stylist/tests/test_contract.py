import json
from pathlib import Path

from agents.stylist.agent import StylistAgent
from agents.stylist.contract import StylistInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    StylistInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = StylistAgent()
    assert agent.name == "stylist"
    assert agent.description
