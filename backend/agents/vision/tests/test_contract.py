import json
from pathlib import Path

from agents.vision.agent import VisionAgent
from agents.vision.contract import VisionInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    VisionInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = VisionAgent()
    assert agent.name == "vision"
    assert agent.description
