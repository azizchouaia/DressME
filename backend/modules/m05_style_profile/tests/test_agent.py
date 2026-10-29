"""Style coach agent and POST /preferences. The LLM is a scripted fake: no Ollama needed, deterministic."""

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from modules.m05_style_profile import service, styles
from modules.m05_style_profile.agent import graph, llm
from modules.m05_style_profile.prior import build_prior
from modules.m05_style_profile.router import router

from .test_router import DEMO, onboard


class ScriptedModel(BaseChatModel):
    """Answers the scripted messages in order and records what it was sent."""

    script: list[AIMessage]
    seen: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])


def call(name: str, args: dict, n: int = 0) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{name}_{n}"}])


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def scripted():
    def use(*messages: AIMessage) -> ScriptedModel:
        model = ScriptedModel(script=list(messages), seen=[])
        llm.set_model(model)
        return model

    yield use
    llm.set_model(None)


async def _style_weight(user_id: str, style: str) -> float:
    space = await styles.get_space()
    rec = await service._bandit(user_id, await service._get_profile(user_id), space)
    return float(rec.model.mean[service._layout(space).style_index(style)])


# --- POST /preferences --------------------------------------------------------------------------------


async def test_preferences_move_the_taste_and_keep_the_swipes(client):
    p0 = onboard(client)
    space = await styles.get_space()
    classic = space.vectors[space.ids.index("classic")]
    p = client.post("/m05/preferences", json={"user_id": DEMO, "more": ["classic"]}).json()
    t0, t1 = np.array(p0["taste_vector"]), np.array(p["taste_vector"])
    assert float(t1 @ classic) > float(t0 @ classic)
    assert p["style_mix"]["classic"] > p0["style_mix"]["classic"]
    p = client.post("/m05/preferences", json={"user_id": DEMO, "less": ["classic"]}).json()
    assert p["answers"] == {"want_more": [], "want_less": ["classic"]}
    assert float(np.array(p["taste_vector"]) @ classic) < float(t0 @ classic)
    assert p["n_feedback"] == 10  # the swipes are kept


async def test_preferences_shift_prior_and_keep_learning(client, bandit_mode):
    onboard(client)
    cards = client.post("/m05/choose", json={"user_id": DEMO, "k": 3}).json()["cards"]
    client.post("/m05/feedback", json={"user_id": DEMO, "events": [{"log_id": cards[0]["log_id"], "reaction": "heart"}]})
    before_classic, before_street = await _style_weight(DEMO, "classic"), await _style_weight(DEMO, "streetwear")
    n_before = (await service._bandit(DEMO, None, await styles.get_space())).model.n_updates

    r = client.post("/m05/preferences", json={"user_id": DEMO, "more": ["classic"], "less": ["streetwear"]})
    assert r.status_code == 200, r.text
    p = r.json()
    assert "classic" in p["answers"]["want_more"] and p["answers"]["want_less"] == ["streetwear"]
    assert await _style_weight(DEMO, "classic") > before_classic
    assert await _style_weight(DEMO, "streetwear") < before_street
    assert (await service._bandit(DEMO, None, await styles.get_space())).model.n_updates == n_before  # learning kept
    assert abs(sum(p["style_mix"].values()) - 1) < 1e-3


async def test_preferences_latest_wish_wins(client):
    onboard(client)
    client.post("/m05/preferences", json={"user_id": DEMO, "more": ["streetwear", "classic"]})
    p = client.post("/m05/preferences", json={"user_id": DEMO, "less": ["streetwear"]}).json()
    a = p["answers"]
    assert a == {"want_more": ["classic"], "want_less": ["streetwear"]}
    layout = service._layout(await styles.get_space())
    mean = build_prior(layout, a)
    assert mean[layout.style_index("streetwear")] < 0 < mean[layout.style_index("classic")]


def test_preferences_errors(client):
    assert client.post("/m05/preferences", json={"user_id": DEMO, "more": ["classic"]}).status_code == 404
    client.get("/m05/onboarding/swipe-cards", params={"user_id": DEMO})  # cards shown, none answered yet
    assert client.post("/m05/preferences", json={"user_id": DEMO, "more": ["classic"]}).status_code == 404
    onboard(client)
    assert client.post("/m05/preferences", json={"user_id": DEMO, "more": ["gothic"]}).status_code == 422
    assert client.post("/m05/preferences", json={"user_id": DEMO}).status_code == 422
    both = {"user_id": DEMO, "more": ["classic"], "less": ["classic"]}
    assert client.post("/m05/preferences", json=both).status_code == 422


# --- agent ----------------------------------------------------------------------------------------------


def test_agent_more_classic_scenario(client, scripted):
    onboard(client)
    model = scripted(
        call("explain_my_recommendations", {}),
        call("update_style_preferences", {"more": ["classic"], "less": ["streetwear"]}),
        call("recommend_outfits", {"occasion": "casual", "temp_c": 20}),
        AIMessage("C'est noté : plus de classique, moins de streetwear. Voici 3 tenues."),
    )
    r = client.post(
        "/m05/agent/chat",
        json={"user_id": DEMO, "message": "Pourquoi du streetwear ? Je veux plus classique."},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert [s["tool"] for s in out["steps"]] == [
        "explain_my_recommendations",
        "update_style_preferences",
        "recommend_outfits",
    ]
    assert out["steps"][0]["result"].startswith("rules learnt")
    assert out["steps"][1]["result"].startswith("Applied")
    assert out["profile_changed"] is True
    assert 1 <= len(out["cards"]) <= 3 and out["cards"][0]["log_id"]
    assert out["reply"].startswith("C'est noté")
    assert "classic" in client.get(f"/m05/profile/{DEMO}").json()["answers"]["want_more"]
    # the profile is recalled into the system prompt, and refreshed after the update
    first, last = model.seen[0][0].content, model.seen[-1][0].content
    assert "STYLE CATALOGUE" in first and "- classic: Classic" in first
    assert "asked for more: none" in first and "asked for more: Classic" in last


def test_agent_runs_a_repeated_tool_call_once(client, scripted):
    onboard(client)
    twice = AIMessage(
        "",
        tool_calls=[
            {"name": "update_style_preferences", "args": {"more": ["classic"]}, "id": "a"},
            {"name": "update_style_preferences", "args": {"more": ["classic"]}, "id": "b"},
        ],
    )
    scripted(twice, AIMessage("ok"))
    out = client.post("/m05/agent/chat", json={"user_id": DEMO, "message": "plus classique"}).json()
    assert [s["tool"] for s in out["steps"]] == ["update_style_preferences"]


def test_agent_remembers_the_thread(client, scripted):
    onboard(client)
    model = scripted(AIMessage("Bonjour !"), AIMessage("Vous m'avez dit bonjour."))
    first = client.post("/m05/agent/chat", json={"user_id": DEMO, "message": "Salut"}).json()
    second = client.post(
        "/m05/agent/chat", json={"user_id": DEMO, "message": "Qu'ai-je dit ?", "thread_id": first["thread_id"]}
    ).json()
    assert second["thread_id"] == first["thread_id"] and second["steps"] == []
    sent = [m.content for m in model.seen[1][1:]]
    assert sent == ["Salut", "Bonjour !", "Qu'ai-je dit ?"]


def test_agent_bad_style_is_reported_to_the_llm(client, scripted):
    onboard(client)
    scripted(call("update_style_preferences", {"more": ["gothic"]}), AIMessage("Ce style n'existe pas."))
    out = client.post("/m05/agent/chat", json={"user_id": DEMO, "message": "plus gothique"}).json()
    assert out["steps"][0]["result"].startswith("Not applied") and "classic" in out["steps"][0]["result"]
    assert out["profile_changed"] is False


def test_agent_before_the_first_swipes(client, scripted):
    model = scripted(call("get_style_profile", {}), AIMessage("Swipe d'abord quelques cartes !"))
    out = client.post("/m05/agent/chat", json={"user_id": DEMO, "message": "c'est quoi mon style ?"}).json()
    assert out["steps"][0]["result"].startswith("The user has no style profile yet")
    assert "must swipe the first cards" in model.seen[0][0].content and out["profile_changed"] is False


def test_agent_llm_down_is_503(client, monkeypatch):
    import httpx

    class Down(ScriptedModel):
        def _generate(self, *a, **k):
            raise httpx.ConnectError("connection refused")

    llm.set_model(Down(script=[], seen=[]))
    try:
        r = client.post("/m05/agent/chat", json={"user_id": DEMO, "message": "hello"})
    finally:
        llm.set_model(None)
    assert r.status_code == 503 and "LLM unavailable" in r.json()["detail"]


def test_tools_are_bound_to_the_user():
    from modules.m05_style_profile.agent.tools import build_tools

    for t in build_tools(DEMO):
        assert "user_id" not in t.args  # the LLM can never pick another user's profile


def test_pipeline_graph_shape():
    g = graph.build_graph(DEMO).get_graph()
    assert {"recall_profile", "coach", "tools"} <= set(g.nodes)
    assert "recall_profile" in g.draw_mermaid()

