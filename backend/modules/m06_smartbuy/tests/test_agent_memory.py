"""Smart Buy as an agent: identity, memory, answer without a new photo, feedback, next actions."""

import asyncio

import pytest

from modules.m06_smartbuy.agent import CONFIG, SmartBuyAgent
from modules.m06_smartbuy.memory import AgentMemory


@pytest.fixture()
def agent(tmp_path):
    return SmartBuyAgent({**CONFIG, "real": [], "personalize": False}, memory=AgentMemory(tmp_path))


def run(agent, **kw):
    return asyncio.run(agent({"user_id": "usr_sarra", **kw}))


def test_identity_card_and_tool_description(agent):
    card = agent.card()
    assert card["name"] == "smartbuy" and "when_to_use" in card
    assert "question" in agent.description and "next_actions" in agent.description


def test_decision_is_remembered_with_next_actions(agent):
    out = run(agent, probe_image="custom:shirt:white", price_tnd=70, session_id="s1")
    assert out["decision_id"] and out["agent"]["name"] == "smartbuy"
    assert out["next_actions"][-1]["action"] == "feedback"
    assert agent.memory.history("usr_sarra")[0]["decision_id"] == out["decision_id"]


def test_answer_reuses_the_request_from_memory(agent):
    first = run(agent, probe_image="custom:shirt:navy", price_tnd=60, session_id="s2")
    assert first["question_key"] == "need_for_occasion" and first["next_actions"][0]["action"] == "ask_user"
    out = run(agent, session_id="s2", answer={"question_key": "need_for_occasion", "value": True})
    assert out["piece"] == "Navy shirt" and any("answer" in n for n in out["memory_notes"])


def test_answer_without_question_is_refused(agent):
    with pytest.raises(ValueError):
        run(agent, session_id="new", answer={"question_key": "need_for_occasion", "value": True})


def test_same_piece_again_is_noticed_and_feedback_saved(agent):
    first = run(agent, probe_image="custom:jeans:blue", price_tnd=80, session_id="a")
    agent.feedback("usr_sarra", first["decision_id"], bought=True, liked=True)
    again = run(agent, probe_image="custom:jeans:blue", price_tnd=80, session_id="b")
    assert any("before" in n and "bought" in n for n in again["memory_notes"])


def test_body_is_remembered_for_the_next_size_advice(agent):
    body = {"fit_refs": [{"brand": "Medina Atelier", "size": "M", "category": "top", "fit": "normal"}]}
    run(agent, probe_image="custom:shirt:white", price_tnd=70, shop_brand="Medina Atelier", body=body)
    out = run(agent, probe_image="custom:shirt:blue", price_tnd=70, shop_brand="Medina Atelier")
    assert out["size_advice"] and any("saved body" in n for n in out["memory_notes"])


def test_fit_text_gives_a_size(agent):
    agent.config["fit_text_llm"] = False
    out = run(agent, probe_image="custom:shirt:white", price_tnd=70, shop_brand="Medina Atelier",
              body={"fit_text": "I wear M at Medina Atelier, very tight on the shoulders"})
    assert out["size_advice"]["size"] == "L"
    assert any("read from your text" in n for n in out["memory_notes"])
    assert any("shoulder" in n for n in out["memory_notes"])


def test_app_endpoints_meta_and_cors():
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app)
    m = c.get("/m06/meta").json()
    assert m["users"] and "blazer" in m["types"] and m["brands"]
    r = c.options("/m06/meta", headers={"Origin": "http://localhost:5555", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5555"
