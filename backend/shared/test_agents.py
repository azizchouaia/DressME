"""Module agents: cards, envelope, errors, registry, agent-to-agent calls (mocked modules, no models)."""

import asyncio

import pytest

from orchestrator.registry import tool_names
from shared import agent_bus

MINE = {"m02_recommendation", "m03_wear_log", "m04_scheduler", "m17_capsule", "m09_avatar_3d"}


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    for m in ("M02", "M03", "M04", "M17", "M09"):
        monkeypatch.setenv(f"{m}_USE_MOCK", "true")


def test_every_module_has_an_agent_and_a_tool():
    assert MINE <= set(agent_bus.agents())
    tools = set(tool_names())
    assert {"m02_recommendation", "m03_wear_log", "m04_scheduler", "m17_capsule", "m09_avatar_3d"} <= tools


def test_cards_describe_actions_and_payloads():
    cards = {c["agent"]: c for c in agent_bus.directory()}
    rec = cards["m02_recommendation"]
    assert "recommend" in rec["actions"] and "context" in rec["actions"]["recommend"]["payload"]
    assert cards["m17_capsule"]["depends_on"] == ["m02_recommendation", "m04_scheduler"]


def test_agent_to_agent_call_and_errors():
    res = asyncio.run(
        agent_bus.ask(
            "m02_recommendation",
            "recommend",
            {"context": {"occasion": "work"}},
            user_id="demo_f",
            sender="m06_smartbuy",
        )
    )
    assert res["ok"] and res["agent"] == "m02_recommendation" and res["mocked"] is True
    bad = asyncio.run(agent_bus.ask("m03_wear_log", "fly"))
    assert not bad["ok"] and "available" in bad["error"]
    with pytest.raises(KeyError):
        asyncio.run(agent_bus.ask("nobody", "x"))


def test_langchain_tools_build():
    from modules.m02_recommendation.tool import tool

    assert tool.name == "m02_recommendation" and "action" in tool.args
