import json
from pathlib import Path

from agents.smartbuy.agent import SmartBuyAgent
from agents.smartbuy.contract import SmartBuyInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    SmartBuyInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = SmartBuyAgent()
    assert agent.name == "smartbuy"
    assert agent.description
