"""BO1 / BO2 agents with a scripted LLM (no Ollama): cards, two-stage routing, cross-BO delegation,
structured calls, session blackboard, guardrails, questions. Modules run on their mocks."""

import asyncio
import json

import pytest

from shared import agent_bus, agent_memory, local_llm
from shared.idea_agent import IdeaAgent

BO1 = (
    "daily_outfit",
    "rotation",
    "forgotten",
    "capsule",
    "seasonal_refresh",
    "avatar_preview",
    "gap_filling",
    "travel",
    "style_insights",
)
BO2 = ("daily_plan", "swap", "laundry", "event_looks", "local_shops", "photo_piece", "declutter")


PIECES = [
    ("t_black", "black t-shirt", "top", "black", "#111111"),
    ("t_white", "white shirt", "top", "white", "#f5f5f5"),
    ("b_blue", "blue jeans", "bottom", "blue", "#3355aa"),
    ("b_yellow", "yellow pants", "bottom", "yellow", "#e8c440"),
    ("s_white", "white sneakers", "shoes", "white", "#fafafa"),
    ("o_navy", "navy jacket", "outerwear", "navy", "#1f2a44"),
]


async def fake_catalog(user):
    """Small built-in wardrobe: the agent tests do not need M2's downloaded model files (ml/models)."""
    items = [{"id": i, "name": n, "category": c} for i, n, c, _, _ in PIECES]
    m2 = [
        {
            "item_id": i,
            "user_id": user,
            "image_raw": "",
            "category": c,
            "colors": [{"name": col, "hex": hx, "share": 1.0}],
            "embedding": [float(k == j) for j in range(1024)],
        }
        for k, (i, _, c, col, hx) in enumerate(PIECES)
    ]
    return {"source": "test wardrobe", "items": items, "m2_items": m2}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_memory, "DATA", tmp_path)
    for m in ("M02", "M03", "M04", "M17", "M09", "M07"):
        monkeypatch.setenv(f"{m}_USE_MOCK", "true")
    from shared import wardrobe

    monkeypatch.setattr(wardrobe, "catalog", fake_catalog)


def llm_script(monkeypatch, replies):
    seen = []

    def fake(messages, tools=None, temperature=0.2, fmt=None):
        seen.append(messages)
        return {"role": "assistant", "content": replies.pop(0) if replies else "ok"}

    monkeypatch.setattr(local_llm, "chat", fake)
    return seen


def call(agent, message="", **payload):
    return asyncio.run(
        agent_bus.get(agent)({"user_id": "demo_f", "session_id": "t", "message": message, "payload": payload})
    )


def test_every_idea_has_an_agent_with_a_card():
    names = set(agent_bus.agents())
    assert set(BO1) | set(BO2) | {"personalised_recommendations", "time_optimisation"} <= names
    for n in BO1 + BO2:
        a = agent_bus.get(n)
        assert isinstance(a, IdeaAgent) and a.CARD["ideas"] and a.actions()
        assert {"name", "role", "when_to_use", "skills"} <= set(a.card())


def test_structured_call_skips_the_llm(monkeypatch):
    seen = llm_script(monkeypatch, [])
    r = call("laundry", action="status", reply=False)
    assert r["agent"] == "laundry" and r["result"]["action"] == "status" and not seen


def test_two_stage_routing_with_cross_bo(monkeypatch):
    # BO2 orchestrator -> guardrail -> BO1 orchestrator -> forgotten agent (its LLM picks the action) ->
    # answer
    llm_script(
        monkeypatch, ['{"action": "rediscover", "args": {"days": 30}}', "Here are your forgotten pieces."]
    )
    r = call("time_optimisation", "show me pieces I haven't worn in a long time")
    res = r["result"]
    assert res["data"]["handled_by"].startswith("personalised_recommendations")
    assert res["reply"] == "Here are your forgotten pieces."
    flat = json.dumps(res["steps"])
    assert '"to": "personalised_recommendations"' in flat and '"to": "forgotten"' in flat


def test_llm_picks_the_agent_then_the_action(monkeypatch):
    llm_script(
        monkeypatch, ['{"agent": "capsule"}', '{"action": "build", "args": {"size": 6}}', "Your capsule."]
    )
    r = call("personalised_recommendations", "I want a small minimal wardrobe")
    route = [s for s in r["result"]["steps"] if s["step"] == "llm_route"]
    assert route and route[0]["decision"] == "capsule"
    assert r["result"]["data"]["handled_by"] == "capsule.build"


def test_session_blackboard_lets_swap_follow_an_outfit(monkeypatch):
    llm_script(monkeypatch, [])
    call("daily_outfit", action="recommend", reply=False)
    from shared.idea_agent import get_state

    assert get_state("demo_f", "t").get("last_outfit") is not None


def test_questions_come_back(monkeypatch):
    llm_script(monkeypatch, ['{"action": "plan", "args": {}}'])
    r = call("travel", "I want to travel")
    assert r["question"]


def test_unknown_action_is_an_answer_not_a_crash(monkeypatch):
    llm_script(monkeypatch, [])
    r = call("swap", action="fly")
    assert "unknown action" in r["result"]["error"]


def test_stated_taste_is_saved_in_long_term_memory(monkeypatch):
    # 1 extraction (memory write), 2 orchestrator routing, 3 idea routing, 4 answer
    llm_script(
        monkeypatch,
        [
            '{"kind": "dislikes", "value": "yellow"}',
            '{"agent": "daily_outfit"}',
            '{"action": "recommend", "args": {}}',
            "Here is an outfit without yellow.",
        ],
    )
    out = call("personalised_recommendations", "I hate yellow, what should I wear today?")
    assert agent_memory.profile("demo_f")["dislikes"] == ["yellow"]
    assert any(s["step"] == "memory_write" for s in out["result"]["steps"])
    # sub-agents (reply False) never write it a second time
    assert agent_memory.profile("demo_f")["dislikes"].count("yellow") == 1
