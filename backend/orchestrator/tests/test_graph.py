"""The orchestrator loop, with a scripted planner and a stand-in agent."""

import asyncio

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from orchestrator.graph import build_graph, run_turn


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        if not self.replies:
            raise AssertionError("the graph called the model more times than the script")
        return self.replies.pop(0)


def tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def probe_tool(seen):
    async def probe(user_id: str, session_id: str = "", answer: str | None = None) -> dict:
        seen.append({"user_id": user_id, "session_id": session_id, "answer": answer})
        if not answer:
            return {"question": "Is this for a wedding?"}
        return {
            "verdict": "buy",
            "score": 80,
            "next_actions": [{"action": "show_outfits", "label": "See outfits", "tool": "stylist", "args": {}}],
        }

    return StructuredTool.from_function(
        coroutine=probe,
        name="probe",
        description="Stand-in purchase agent.",
    )


def test_question_then_same_agent_keeps_the_verdict():
    seen = []
    model = Scripted(
        [
            tool_call("probe", {"user_id": "ada"}, "c1"),
            tool_call("probe", {"user_id": "ada", "answer": "yes, a wedding"}, "c2"),
            AIMessage(content="I would skip this. score 1"),  # the writer contradicts the agent -> replaced
        ]
    )
    graph = build_graph(model=model, tools=[probe_tool(seen)])

    first = asyncio.run(run_turn(graph, user_id="ada", session_id="wedding", message="Should I buy this jacket?"))
    assert first["reply"] == "Is this for a wedding?"
    assert first["question"] == "Is this for a wedding?"
    assert seen[0]["session_id"] == "wedding"

    second = asyncio.run(run_turn(graph, user_id="ada", session_id="wedding", message="yes, a wedding"))
    assert second["reply"] == "verdict: buy. score: 80. next: See outfits."
    assert "skip" not in second["reply"]
    assert seen[1]["answer"] == "yes, a wedding"
    assert seen[1]["session_id"] == "wedding"
    assert second["last_agent"] == "probe"


def test_tool_calls_stop_at_three():
    async def again(user_id: str, session_id: str = "") -> dict:
        return {
            "verdict": "think",
            "score": 50,
            "next_actions": [{"action": "again", "label": "Again", "tool": "again", "args": {}, "auto": True}],
        }

    tool = StructuredTool.from_function(coroutine=again, name="again", description="Loops on purpose.")
    calls = [tool_call("again", {"user_id": "ada"}, f"c{i}") for i in range(3)]
    model = Scripted([*calls, AIMessage(content="verdict: think score: 50")])
    graph = build_graph(model=model, tools=[tool])
    out = asyncio.run(run_turn(graph, user_id="ada", session_id="loop", message="keep going"))
    assert "verdict: think" in out["reply"]
    assert "score: 50" in out["reply"]
    assert model.replies == []


def test_next_actions_are_offered_not_chained_unless_auto():
    async def once(user_id: str, session_id: str = "") -> dict:
        return {"verdict": "think", "score": 50,
                "next_actions": [{"action": "find_cheaper", "label": "Find it cheaper", "tool": "localshop", "args": {}}]}

    tool = StructuredTool.from_function(coroutine=once, name="once", description="One call.")
    model = Scripted([tool_call("once", {"user_id": "ada"}, "c1"), AIMessage(content="Think twice: score 50.")])
    out = asyncio.run(run_turn(build_graph(model=model, tools=[tool]), user_id="ada", session_id="s", message="buy?"))
    assert model.replies == []
    assert out["next_actions"][0]["label"] == "Find it cheaper"


def test_question_key_is_given_to_the_planner_on_the_answer():
    seen_systems = []

    class Spy(Scripted):
        async def ainvoke(self, messages):
            seen_systems.append(messages[0][1] if isinstance(messages[0], tuple) else "")
            return await super().ainvoke(messages)

    async def asks(user_id: str, session_id: str = "", answer: dict | None = None) -> dict:
        if not answer:
            return {"question": "Do you need it for an occasion?", "question_key": "need_for_occasion"}
        return {"verdict": "buy", "score": 70}

    tool = StructuredTool.from_function(coroutine=asks, name="smartbuy", description="Buy agent.")
    model = Spy([tool_call("smartbuy", {"user_id": "ada"}, "c1"),
                 tool_call("smartbuy", {"user_id": "ada", "answer": {"question_key": "need_for_occasion", "value": True}}, "c2"),
                 AIMessage(content="Buy it, score 70.")])
    graph = build_graph(model=model, tools=[tool])
    asyncio.run(run_turn(graph, user_id="ada", session_id="q", message="buy this?"))
    out = asyncio.run(run_turn(graph, user_id="ada", session_id="q", message="yes"))
    assert "need_for_occasion" in seen_systems[1] and "smartbuy" in seen_systems[1]
    assert out["reply"] == "Buy it, score 70." and out["question"] is None


def test_good_reply_missing_a_number_is_kept_and_completed():
    from orchestrator.graph import enforce_facts
    assert enforce_facts("Good buy! Score 80.", {"verdict": "buy", "score": 80}) == "Good buy! Score 80."
    assert enforce_facts("This is a good buy.", {"verdict": "buy", "score": 80}) == "This is a good buy. (score: 80)"
    assert enforce_facts("Skip it.", {"verdict": "buy", "score": 80}).startswith("verdict: buy")
