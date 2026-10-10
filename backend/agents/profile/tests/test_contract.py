import json
from pathlib import Path

from agents.profile.agent import ProfileAgent
from agents.profile.contract import ProfileInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    ProfileInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = ProfileAgent()
    assert agent.name == "profile"
    assert agent.description
