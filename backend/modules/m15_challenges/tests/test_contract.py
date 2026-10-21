import json
from pathlib import Path

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.contract import Challenge, ChallengesInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    ChallengesInput.model_validate(FIXTURE)


def test_agent_metadata():
    agent = ChallengesAgent()
    assert agent.name == "challenges"
    assert agent.description


def test_seed_challenges_are_valid():
    agent = ChallengesAgent()
    assert {"ch_7x7", "ch_mono", "ch_jebba", "ch_10x10", "ch_local"} <= set(agent.store.challenges)
    for ch in agent.store.challenges.values():
        Challenge.model_validate(ch.model_dump())
