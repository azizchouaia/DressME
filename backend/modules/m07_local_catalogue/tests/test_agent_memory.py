"""BO6 agent shape (DressMe Agent Guide): card, question + answer, memory, next page, next_actions, forget."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import router as m07_router
from modules.m07_local_catalogue import service, tool
from modules.m07_local_catalogue.agent import LocalShopAgent, gender_answer
from modules.m07_local_catalogue.contract import LocalShopInput, LocalShopOutput
from modules.m07_local_catalogue.identity import CARD
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from shared.base_agent import AgentError

from .test_search import EN, ROWS, FakeEncoder, product

# Sneakers for women and for men: a request that names neither gets the gender question.
GENDERED = [
    {
        **product("w1", "Baskets femme", "sneakers", "shoes", "white", 90, "Tunis", "Tunis", "Baskets"),
        "gender": "women",
    },
    {
        **product("m1", "Baskets homme", "sneakers", "shoes", "white", 95, "Tunis", "Tunis", "Baskets"),
        "gender": "men",
    },
    {
        **product("m2", "Baskets cuir homme", "sneakers", "shoes", "black", 85, "Sfax", "Sfax", "Baskets"),
        "gender": "men",
    },
]


@pytest.fixture
def agent():
    rows = ROWS + GENDERED
    enc = FakeEncoder()
    emb = enc.encode_texts([f"a photo of {r['color']} {EN[r['subcategory']]}" for r in rows])
    return LocalShopAgent(catalogue=Catalogue.from_records(rows, emb), encoder=enc)


@pytest.fixture
def client(agent, monkeypatch):
    monkeypatch.setattr(service, "knowledge_base_ready", lambda: True)
    monkeypatch.setattr(service, "_agent", agent)
    monkeypatch.setattr(service, "_memory", agent.memory)
    app = FastAPI()
    app.include_router(m07_router.router)
    return TestClient(app)


def call(agent, **payload):
    return asyncio.run(agent(payload))


def actions(out):
    return {a["action"]: a for a in out["next_actions"]}


# ---- card + contract
def test_card_and_tool_built_from_it(client):
    card = client.get("/m07/card").json()
    assert card["name"] == "localshop" == tool.tool.name and card["owner"] == "BO6"
    assert {"when_to_use", "when_not_to_use", "skills", "rules"} <= card.keys()
    assert "boutique" in card["skills"]  # M14 is a skill of the BO6 agent, not another agent
    assert client.get("/m07/identity").json() == CARD
    assert "smartbuy" in tool.tool.description and "session_id" in tool.tool.description


def test_answer_or_next_page_alone_is_a_valid_input():
    LocalShopInput.model_validate({"answer": {"value": "femme"}, "session_id": "s1"})
    LocalShopInput.model_validate({"next_page": True, "session_id": "s1"})


def test_output_has_agent_fields(agent):
    out = call(agent, query="chemise en lin blanche", user_id="u1", session_id="s1")
    LocalShopOutput.model_validate(out)
    assert out["agent"] == {"name": "localshop", "version": CARD["version"]}
    assert out["session_id"] == "s1" and out["decision_id"].startswith("loc_")


# ---- question -> answer (same session, request not repeated)
def test_gender_question_then_answer_then_remembered(agent):
    out = call(agent, query="baskets", user_id="u1", session_id="s1")
    assert out["question"] == "Pour femme ou pour homme ?" and out["question_key"] == "gender"
    ask = out["next_actions"][0]
    assert ask["action"] == "ask_user" and ask["tool"] == "localshop"
    assert ask["args"] == {"session_id": "s1", "answer": {"question_key": "gender"}}

    out = call(agent, answer={"value": "femme"}, user_id="u1", session_id="s1")
    ids = [r["product_id"] for r in out["results"]]
    assert "w1" in ids and not {"m1", "m2"} & set(ids)  # pieces known to be for men are gone
    assert out["question"] is None and out["parsed"]["gender"] == "women"
    assert "femme" in out["memory_notes"][0]

    # Long-term memory: the next search of this user, in another chat, is not asked again.
    out = call(agent, query="baskets", user_id="u1", session_id="s2")
    assert out["question"] is None and out["parsed"]["gender"] == "women"
    assert "mémoire" in out["memory_notes"][0]

    # What the text says still wins over the memory.
    out = call(agent, query="baskets pour mon mari", user_id="u1", session_id="s3")
    assert out["parsed"]["gender"] == "men" and out["memory_notes"] == []


def test_remembered_gender_skipped_for_pieces_that_gender_has_none_of(agent):
    call(agent, query="baskets", user_id="u4", session_id="s1")
    call(agent, answer={"value": "homme"}, user_id="u4", session_id="s1")
    # The only shirt is for women (one men's shirt in 20 would be a mistake, not a men's type).
    rows = [{**r, "gender": "women"} if r["product_id"] == "p5" else r for r in ROWS + GENDERED]
    agent.catalogue = Catalogue.from_records(rows, agent.catalogue.embeddings)
    out = call(agent, query="chemise en lin blanche", user_id="u4", session_id="s2")
    assert out["parsed"]["gender"] is None and out["memory_notes"] == []
    assert [r["product_id"] for r in out["results"]] == ["p5"]


@pytest.mark.parametrize(
    ("said", "gender"),
    [
        ("femme", "women"),
        ("Pour homme", "men"),
        ("rajel", "men"),
        ("للنساء", "women"),
        ("les deux", "any"),
        ("je sais pas", None),
    ],
)
def test_gender_answers(said, gender):
    assert gender_answer(said) == gender


def test_both_genders_answer_is_never_asked_again(agent):
    call(agent, query="baskets", user_id="u2", session_id="s1")
    out = call(agent, answer={"question_key": "gender", "value": "les deux"}, user_id="u2", session_id="s1")
    assert out["parsed"]["gender"] is None and out["question"] is None
    assert call(agent, query="baskets", user_id="u2", session_id="s2")["question"] is None


def test_budget_question_when_nothing_is_that_cheap(agent):
    out = call(agent, query="baskets max 30 TND", user_id="u1", session_id="s1")
    assert out["results"] == [] and out["question_key"] == "max_price_tnd"
    assert "55 TND" in out["question"]  # the cheapest sneakers, so the user can answer
    out = call(agent, answer={"value": "100 dinars"}, user_id="u1", session_id="s1")
    assert out["parsed"]["max_price_tnd"] == 100 and out["results"]


def test_piece_question_when_nothing_is_understood(agent):
    out = call(agent, query="zzz qwerty", user_id="u1", session_id="s1")
    assert out["results"] == [] and out["question_key"] == "query"
    out = call(agent, answer={"value": "des baskets"}, user_id="u1", session_id="s1")
    assert out["parsed"]["subcategory"] == "sneakers" and out["results"]


def test_answer_without_a_search_in_the_session_is_an_error(agent):
    with pytest.raises(AgentError):
        call(agent, answer={"value": "femme"}, user_id="u1", session_id="never")
    call(agent, query="chemise en lin blanche", user_id="u1", session_id="s1")  # no question asked
    with pytest.raises(AgentError):
        call(agent, answer={"value": "femme"}, user_id="u1", session_id="s1")


def test_bad_answer_is_an_error(agent):
    call(agent, query="baskets", user_id="u1", session_id="s1")
    with pytest.raises(AgentError):
        call(agent, answer={"value": "je sais pas"}, user_id="u1", session_id="s1")


# ---- next page from memory
def test_next_page_continues_the_session_search(agent):
    first = call(agent, query="baskets", gender="women", k=2, user_id="u1", session_id="s1")
    more = actions(first)["more_results"]
    assert more["args"] == {"session_id": "s1", "next_page": True}
    second = call(agent, **more["args"], user_id="u1")
    assert second["results"]
    assert not {r["product_id"] for r in first["results"]} & {r["product_id"] for r in second["results"]}
    assert second["question"] is None  # a question is only asked on the first page


# ---- next_actions for the orchestrator
def test_next_actions_chain_other_agents(agent):
    out = call(agent, query="chemise en lin blanche", user_id="u1", session_id="s1", language="en")
    acts = actions(out)
    top = out["results"][0]
    assert acts["open_shop"]["tool"] is None and acts["open_shop"]["args"]["url"] == top["product_url"]
    assert acts["open_shop"]["label"] == f"See it at {top['shop']}"
    assert acts["judge"]["tool"] == "smartbuy"
    assert acts["judge"]["args"] == {
        "probe_image": top["image_url"],
        "price_tnd": 79,
        "shop_brand": top["shop"],
    }
    assert acts["show_outfits"]["tool"] == "stylist"
    assert acts["feedback"]["args"]["decision_id"] == out["decision_id"]
    assert "more_results" not in acts  # one shirt only


def test_question_in_arabic(agent):
    out = call(agent, query="baskets", user_id="u3", session_id="s1", language="ar")
    assert out["question"] == "للنساء أم للرجال؟"


# ---- long-term memory: file, history, feedback, forget
def test_memory_file_history_feedback_and_forget(client, memory_dir):
    out = client.post("/m07/search", json={"query": "baskets", "user_id": "u9", "session_id": "s1"}).json()
    saved = json.loads((memory_dir / "u9.json").read_text(encoding="utf-8"))
    assert saved["sessions"]["s1"]["question_key"] == "gender"

    history = client.get("/m07/history/u9").json()["history"]
    assert history[0]["decision_id"] == out["decision_id"] and history[0]["request"] == "baskets"

    fb = {"user_id": "u9", "decision_id": out["decision_id"], "useful": True, "bought_product_id": "w1"}
    assert client.post("/m07/feedback", json=fb).json()["feedback"]["bought_product_id"] == "w1"
    assert client.post("/m07/feedback", json={**fb, "decision_id": "loc_unknown"}).status_code == 404

    assert client.delete("/m07/memory/u9").status_code == 204
    assert not (memory_dir / "u9.json").exists() and client.get("/m07/history/u9").json()["history"] == []


def test_anonymous_memory_stays_in_ram(agent, memory_dir):
    call(agent, query="baskets", session_id="s1")
    out = call(agent, answer={"value": "homme"}, session_id="s1")
    assert out["parsed"]["gender"] == "men"
    assert not memory_dir.exists()


def test_next_page_is_logged_with_the_restored_request(client, event_log):
    client.post("/m07/search", json={"query": "baskets", "gender": "women", "k": 1, "user_id": "u1"})
    client.post("/m07/search", json={"next_page": True, "user_id": "u1"})
    first, second = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert second["value"] == "baskets" and second["data"]["offset"] == 1
