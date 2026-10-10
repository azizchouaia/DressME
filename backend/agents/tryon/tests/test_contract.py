import json
from pathlib import Path

from agents.tryon.agent import TryOnAgent
from agents.tryon.contract import TryOnInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    TryOnInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = TryOnAgent()
    assert agent.name == "tryon"
    assert agent.description
