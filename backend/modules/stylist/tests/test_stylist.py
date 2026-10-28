"""Stylist agent with a scripted LLM (no Ollama needed): tool loop, validation, memory, guard, trace."""

import asyncio

import pytest

from modules.stylist import agent as st
from modules.stylist import llm, memory, tools


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DATA", tmp_path)
    for m in ("M02", "M03", "M04", "M17", "M09"):
        monkeypatch.setenv(f"{m}_USE_MOCK", "true")
    cat = {
        "source": "test",
        "m2_items": None,
        "items": [
            {"id": "a", "name": "navy shirt", "category": "top"},
            {"id": "b", "name": "grey pants", "category": "bottom"},
        ],
    }

    async def fake_catalog(user):
        return cat

    monkeypatch.setattr(tools, "catalog", fake_catalog)
    monkeypatch.setattr(tools, "retrieve", lambda q, items, k=6: items[:1])


def script(monkeypatch, replies):
    seen = []

    def fake_chat(messages, tools_=None, temperature=0.2, fmt=None):
        seen.append(messages)
        return replies.pop(0)

    monkeypatch.setattr(llm, "chat", fake_chat)
    return seen


def test_tool_loop_memory_and_trace(monkeypatch):
    seen = script(
        monkeypatch,
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "remember_preference",
                            "arguments": {"kind": "dislikes", "value": "yellow"},
                        }
                    },
                    {
                        "function": {
                            "name": "set_laundry",
                            "arguments": {"pieces": "grey pants", "status": "laundry"},
                        }
                    },
                ],
            },
            {"role": "assistant", "content": "Noted, no yellow. Your grey pants are in the laundry."},
        ],
    )
    out = asyncio.run(st.chat("u1", st.ChatPayload(message="I hate yellow, and my grey pants are dirty")))
    r = out["result"]
    assert r["reply"].startswith("Noted") and r["tools_used"] == ["remember_preference", "set_laundry"]
    assert memory.profile("u1")["dislikes"] == ["yellow"]
    assert [s["step"] for s in r["trace"]][:2] == ["memory", "retrieval"]
    assert any(m["role"] == "tool" for m in seen[1])  # tool results fed back to the LLM
    assert len(memory.history("u1", "default")) == 2  # the turn is remembered
    # next turn: the profile is in the prompt
    script(monkeypatch, [{"role": "assistant", "content": "ok"}])
    seen2 = script(monkeypatch, [{"role": "assistant", "content": "ok"}])
    asyncio.run(st.chat("u1", st.ChatPayload(message="hello")))
    assert "yellow" in seen2[0][1]["content"]


def test_outfit_question_always_uses_m2(monkeypatch):
    seen = script(
        monkeypatch,
        [
            {"role": "assistant", "content": "wear anything"},
            {"role": "assistant", "content": "Wear outfit 1."},
            {"role": "assistant", "content": "Grounded: wear outfit 1."},
        ],
    )
    r = asyncio.run(st.chat("u2", st.ChatPayload(message="what should I wear today?")))["result"]
    assert r["tools_used"] == ["recommend_outfits"]
    assert r["outfits"] and r["reply"] == "Grounded: wear outfit 1."  # final answer from the exact pieces
    assert "FACTS" in seen[-1][1]["content"]


def test_preference_guard(monkeypatch):
    script(
        monkeypatch,
        [
            {"role": "assistant", "content": "Sure."},
            {"role": "assistant", "content": '{"kind": "dislikes", "value": "yellow"}'},
        ],
    )
    r = asyncio.run(st.chat("u4", st.ChatPayload(message="I hate yellow")))["result"]
    assert "remember_preference" in r["tools_used"] and memory.profile("u4")["dislikes"] == ["yellow"]


def test_bad_arguments_are_clamped(monkeypatch):
    box = tools.Toolbox("u3", {"source": "t", "m2_items": None, "items": []})
    assert tools._pick({"enum": ["work"]}, tools.OCCASIONS, "casual") == "work"
    assert tools._day({"type": "string"}).isoformat()  # garbage -> today
    assert asyncio.run(box.call("nope", {}))["error"]


def test_agent_is_on_the_bus():
    from shared import agent_bus

    assert "stylist" in agent_bus.agents()
    assert set(agent_bus.get("stylist").actions()) == {"chat", "memory", "forget", "status"}
