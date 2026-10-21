import asyncio

from modules.m09_avatar_3d.agent import TryOnAgent
from modules.m09_avatar_3d.contract import TryOnInput


def test_avatar_agent_wears_the_real_clothes_and_remembers_the_pose():
    agent = TryOnAgent()
    first = asyncio.run(agent.run(TryOnInput(user_id="ada", session_id="look", message="show the shirt and vest")))
    assert first.mocked is False
    assert first.garments == ["shirt", "vest"]
    assert first.pose == "stand"
    assert first.question is None
    assert first.next_actions[0].tool == "share"

    second = asyncio.run(agent.run(TryOnInput(user_id="ada", session_id="look", message="wave")))
    assert second.pose == "wave"
    assert second.garments == ["shirt", "vest"]


def test_avatar_agent_asks_instead_of_inventing_a_dress():
    agent = TryOnAgent()
    turn = asyncio.run(agent.run(TryOnInput(user_id="ada", session_id="other", message="wear a dress")))
    assert turn.question
    assert "dress" not in turn.garments
    assert turn.next_actions == []
