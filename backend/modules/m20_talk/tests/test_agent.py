"""Talk quotes taste and writes a preference onto that user only."""

import asyncio
import json

from modules.m20_talk.agent import TalkAgent
from modules.m20_talk.contract import TalkInput
from shared.taste_agent import learn


def _memory(tmp_path, monkeypatch):
    monkeypatch.setenv("TASTE_DATA", str(tmp_path))
    learn("ada", "coat", "like", title="Navy coat", vector=[0.1] * 512)
    learn("ada", "neon", "dislike", title="neon colors")


def test_without_any_llm_it_still_returns_the_memory(tmp_path, monkeypatch):
    _memory(tmp_path, monkeypatch)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    import modules.m20_talk.agent as talk

    def down(*a, **k):
        raise RuntimeError("ollama off")

    monkeypatch.setattr(talk, "_ask_local", down)
    out = asyncio.run(TalkAgent().run(TalkInput(user_id="ada", message="What fits me?")))
    assert "cannot reach" in out.reply
    assert "Navy coat" in out.loves
    assert "neon colors" in out.avoids
    assert out.remembered == []


def test_a_stated_preference_is_saved_for_that_user(tmp_path, monkeypatch):
    _memory(tmp_path, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test")

    def fake(messages):
        return json.dumps({"reply": "The white dress is a 61 match.", "memories": [{"kind": "like", "text": "white dress"}]})

    monkeypatch.setattr("modules.m20_talk.agent._ask", fake)
    out = asyncio.run(
        TalkAgent().run(
            TalkInput(
                user_id="ada",
                message="Remember that I love a white dress.",
                candidates=[{"id": "dress", "title": "White dress", "vector": [0.1] * 512}],
            )
        )
    )
    assert out.scores["White dress"] >= 0
    assert "white dress" in out.remembered
    assert "white dress" in out.loves
