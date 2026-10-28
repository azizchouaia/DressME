"""BO6 LLM in M7: a fake Qwen answers; the search uses what it read only after the checks."""

import asyncio

import pytest

from modules.m07_local_catalogue import llm
from modules.m07_local_catalogue.pipeline import understand

from .test_search import agent  # noqa: F401  (pytest fixture)


class FakeLLM(llm.LLM):
    def __init__(self, answer):
        super().__init__({"enabled": True, "model": "qwen2.5:7b", "url": "http://fake", "uses": {}})
        self.answer, self.calls = answer, 0

    async def _chat(self, system, user, fmt=None, max_tokens=200):
        self.calls += 1
        return self.answer


@pytest.fixture
def fake(monkeypatch):
    def install(answer):
        f = FakeLLM(answer)
        monkeypatch.setattr(llm, "_llm", f)
        return f

    return install


def call(shop_agent, **payload):
    return asyncio.run(shop_agent(payload))


def test_request_the_rules_miss_is_understood_by_the_llm(agent, fake):  # noqa: F811
    f = fake(
        '{"french": "baskets blanches", "subcategory": "sneakers", "color": "white", "gender": "none", '
        '"max_price_tnd": 80, "city": "Tunis"}'
    )
    out = call(agent, query="n7eb haja nlabesha f sa9aya f tunis a9al men 80", user_id="u1", session_id="s1")
    assert f.calls == 1 and out["parsed"]["understood_by"] == "llm"
    assert out["parsed"]["subcategory"] == "sneakers" and out["parsed"]["max_price_tnd"] == 80
    assert [r["product_id"] for r in out["results"]] == ["p1"]  # white sneakers in Tunis under 80 TND
    assert "Demande comprise avec l'IA (qwen2.5:7b)" in out["note"] and out["question"] is None


def test_llm_not_called_when_the_rules_understand(agent, fake):  # noqa: F811
    f = fake('{"french": "x"}')
    out = call(agent, query="baskets blanches", user_id="u1", session_id="s1")
    assert f.calls == 0 and out["parsed"]["understood_by"] == "rules"


def test_llm_down_keeps_the_rules_answer(agent, fake):  # noqa: F811
    fake(None)  # Ollama not running
    out = call(agent, query="zzz qwerty", user_id="u1", session_id="s1")
    assert out["results"] == [] and out["question_key"] == "query"  # same as without LLM


def test_invented_budget_and_city_and_unknown_type_are_dropped():
    raw = {
        "french": "robe",
        "subcategory": "spacesuit",
        "color": "white",
        "gender": "women",
        "max_price_tnd": 300,
        "city": "Sfax",
    }
    slots = understand.check(raw, "nheb robe bidha l 3ers")  # no number, no city in the request
    assert slots == {"query": "robe", "color": "white"}  # "women" is not said in the request: dropped
    assert understand.check({"gender": "women"}, "robe pour ma femme") == {"gender": "women"}
    assert understand.check({"max_price_tnd": 150, "city": "Sousse"}, "robe a9al men 150 alf f sousse") == {
        "max_price_tnd": 150.0,
        "city": "Sousse",
    }


def test_numbers_check():
    assert llm.numbers_ok("94 recherches à 70 TND", "theme: 94 searches, budget 70")
    assert not llm.numbers_ok("120 recherches", "theme: 94 searches")
