"""Graph loaded by the local LangGraph viewer.

The stand-in agent asks one question, then returns a fixed verdict, so the
viewer can light up each node without an API key.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool

from orchestrator.graph import build_graph


async def probe(user_id: str, session_id: str = "", answer: str | None = None) -> dict:
    """Stand-in purchase agent used only in the viewer."""

    if not answer:
        return {"question": "Is this for a wedding?"}
    return {
        "verdict": "buy",
        "score": 80,
        "next_actions": [{"action": "show_outfits", "label": "See outfits", "tool": "stylist", "args": {}}],
    }


tool = StructuredTool.from_function(coroutine=probe, name="probe", description="Stand-in purchase agent.")


class DemoModel:
    """Follows the same path the tests use: ask, then keep the agent's verdict."""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        system = messages[0][1] if messages and isinstance(messages[0], tuple) else ""
        if "Write the user-facing reply" in system:
            return AIMessage(content="verdict: buy. score: 80. next: See outfits.")
        humans = [item for item in messages if isinstance(item, HumanMessage)]
        tools_done = [item for item in messages if isinstance(item, ToolMessage)]
        last_tool = tools_done[-1].content if tools_done else ""
        if "verdict" in str(last_tool):
            return AIMessage(content="See outfits")
        if not tools_done:
            return AIMessage(
                content="",
                tool_calls=[{"name": "probe", "args": {"user_id": "demo"}, "id": "studio-1"}],
            )
        answer = humans[-1].content if humans else ""
        return AIMessage(
            content="",
            tool_calls=[{"name": "probe", "args": {"user_id": "demo", "answer": answer}, "id": "studio-2"}],
        )


graph = build_graph(model=DemoModel(), tools=[tool], checkpointer=False)
