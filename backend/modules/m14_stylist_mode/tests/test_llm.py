"""BO6 LLM in M14: a fake Qwen answers by prompt; its text is used only after the checks."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import llm
from modules.m14_stylist_mode import router as m14_router
from modules.m14_stylist_mode import service
from modules.m14_stylist_mode.simulate import pros, traffic


class FakeQwen(llm.LLM):
    """Answers by the system prompt it gets: escalation JSON, stylist sentence or boutique tips."""

    def __init__(self, escalation=None, sentence=None, tips=None):
        super().__init__({"enabled": True, "model": "qwen2.5:7b", "url": "http://fake", "uses": {}})
        self.answers = {"real person": escalation, "human fashion stylist": sentence, "boutique": tips}
        self.calls: list[str] = []

    async def _chat(self, system, user, fmt=None, max_tokens=200):
        for key, answer in self.answers.items():
            if key in system:
                self.calls.append(key)
                return answer
        return None


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(m14_router.router)
    asyncio.run(pros.seed())
    return TestClient(app)


def user(*texts):
    return [{"role": "user", "text": t} for t in texts]


def test_llm_sentence_replaces_the_raw_request_in_the_summary(api, monkeypatch):
    qwen = FakeQwen(
        sentence="The client wants an outfit for the wedding of a sister in Sousse and asks for a stylist."
    )
    monkeypatch.setattr(llm, "_llm", qwen)
    body = {
        "user_id": "usr_201",
        "session_id": "c1",
        "messages": user("n7eb lebsa l 3ers o5ti f Sousse, budget 250 dt", "n7eb nahki m3a bnadem"),
    }
    h = api.post("/m14/handoff", json=body).json()
    assert h["summary"][0].startswith("Summary (AI): The client wants an outfit")
    assert "Occasion: wedding · budget: 250 TND · city: Sousse" in h["summary"]  # facts stay from code


def test_llm_sentence_with_an_invented_number_is_dropped(api, monkeypatch):
    monkeypatch.setattr(llm, "_llm", FakeQwen(sentence="The client wants a 400 TND dress for a wedding."))
    body = {
        "user_id": "usr_202",
        "session_id": "c2",
        "messages": user("je veux une styliste pour un mariage"),
    }
    h = api.post("/m14/handoff", json=body).json()
    assert h["summary"][0].startswith("Request: ")  # the client never wrote 400: template kept


def test_llm_escalates_a_longer_chat_the_rules_miss(api, monkeypatch):
    qwen = FakeQwen(
        escalation='{"asks_human": true, "frustrated": false, "important_occasion": false, '
        '"evidence": "chkoun ynajem y3awenni"}'
    )
    monkeypatch.setattr(llm, "_llm", qwen)
    msgs = user("sma3ni chkoun ynajem y3awenni", "7ajti b chkoun ya3ref lmoda")
    out = api.post("/m14/handoff/check", json={"user_id": "u", "messages": msgs}).json()
    assert out["escalate"] and out["by_llm"] and out["reason"] == "asks_human"

    qwen.calls.clear()
    out = api.post("/m14/handoff/check", json={"user_id": "u", "messages": user("robe noire")}).json()
    assert not out["escalate"] and qwen.calls == []  # a one-line request is the assistant's job


def test_insights_from_llm_keep_only_tips_with_real_numbers(isolated, m7_agent, monkeypatch):
    asyncio.run(traffic.run(40, 12, seed=3, agent=m7_agent, path=isolated["sim_log"]))
    d = asyncio.run(service.get_dashboard(None, 30))
    gold = next(u for u in d["unmet"] if "Sandals" in u["label"])
    tips = f"- Add gold sandals: {gold['n_searches']} searches.\n- Run 999 promotions tomorrow."
    monkeypatch.setattr(llm, "_llm", FakeQwen(tips=tips))
    out = asyncio.run(service.get_insights(None, 30))
    assert out["source"] == "llm" and out["model"] == "qwen2.5:7b"
    assert out["insights"] == [f"Add gold sandals: {gold['n_searches']} searches."]  # 999 dropped


def test_insights_without_llm_are_rule_based(isolated, m7_agent):
    asyncio.run(traffic.run(40, 12, seed=3, agent=m7_agent, path=isolated["sim_log"]))
    out = asyncio.run(service.get_insights(None, 30))
    assert out["source"] == "rules" and out["insights"] and out["facts"]


def test_llm_signal_without_a_real_quote_is_ignored(api, monkeypatch):
    qwen = FakeQwen(
        escalation='{"asks_human": true, "frustrated": false, "important_occasion": false, '
        '"evidence": "je veux parler a un humain"}'
    )
    monkeypatch.setattr(llm, "_llm", qwen)
    msgs = user("je cherche une robe rouge pour samedi", "merci c'est parfait")
    out = api.post("/m14/handoff/check", json={"user_id": "u", "messages": msgs}).json()
    assert qwen.calls == ["real person"] and not out["escalate"] and not out["by_llm"]  # quote not in chat
