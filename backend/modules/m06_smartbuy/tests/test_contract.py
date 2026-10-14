import json
from pathlib import Path

from modules.m06_smartbuy.agent import SmartBuyAgent
from modules.m06_smartbuy.contract import SmartBuyInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    SmartBuyInput.model_validate(FIXTURE)


def test_agent_metadata():
    a = SmartBuyAgent()
    assert a.name == "smartbuy" and a.description
