import json
from pathlib import Path

from agents.localshop.agent import LocalShopAgent
from agents.localshop.contract import LocalShopInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    LocalShopInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = LocalShopAgent()
    assert agent.name == "localshop"
    assert agent.description
