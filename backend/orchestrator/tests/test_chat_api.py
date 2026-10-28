"""The app's single entry: /chat/message runs the orchestrator; /chat/agents lists the cards."""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from api.main import app
from api.routes import chat
from orchestrator.graph import build_graph
from orchestrator.registry import get_tools


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self.replies.pop(0)


def test_chat_message_calls_the_real_smartbuy_agent(monkeypatch):
    call = AIMessage(content="", tool_calls=[{"name": "smartbuy", "id": "c1",
                                             "args": {"probe_image": "custom:blazer:navy", "price_tnd": 120}}])
    model = Scripted([call, AIMessage(content="ok")])
    monkeypatch.setattr(chat, "_graph", build_graph(model=model, tools=get_tools()))
    r = TestClient(app).post("/chat/message", json={"user_id": "usr_demo", "session_id": "t1", "message": "buy this blazer?"})
    assert r.status_code == 200
    body = r.json()
    assert body["last_agent"] == "smartbuy"
    assert body["cards"][0]["verdict"] in {"buy", "think", "skip"}
    assert body["cards"][0]["verdict"] in body["reply"].lower() or body["question"]


def test_chat_agents_lists_every_agent():
    names = {c["name"] for c in TestClient(app).get("/chat/agents").json()["agents"]}
    assert {"wardrobe", "stylist", "smartbuy", "localshop", "tryon", "share", "challenges", "taste", "talk"} <= names
