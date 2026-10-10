"""Orchestrator graph: LLM with tool calling + tool node, looping until done."""

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from shared.llm import get_chat_model

from .prompts import SYSTEM_PROMPT
from .registry import get_tools
from .state import ChatState


def build_graph():
    tools = get_tools()
    llm = get_chat_model().bind_tools(tools)

    async def assistant(state: ChatState):
        msgs = [("system", SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [await llm.ainvoke(msgs)]}

    g = StateGraph(ChatState)
    g.add_node("assistant", assistant)
    g.add_node("tools", ToolNode(tools))
    g.set_entry_point("assistant")
    g.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "assistant")
    return g.compile()
