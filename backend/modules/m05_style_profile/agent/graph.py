"""Pipeline of the style coach (LangGraph):

    user message -> recall_profile -> coach (LLM) --tool calls--> tools -> recall_profile -> coach ... -> reply

The coach works on a profile learnt from the swipes (no onboarding conversation: a new user swipes cards
first). Tools: get_style_profile, explain_my_recommendations, update_style_preferences, recommend_outfits.

- recall_profile: long-term memory. Reads the M5 profile (style mix, wishes, reactions) from the store and
  puts it into the system prompt; it runs again after every tool round, so the LLM always sees the
  profile as it is now (e.g. right after update_style_preferences).
- coach: the LLM with the 4 tools bound; it sees the system prompt + the last `history_messages` messages.
- tools: runs the tool calls on M5's service (user id bound, see tools.py).
- short-term memory: a checkpointer keeps every conversation by thread id (user id + thread).
"""

import re
import time
import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, trim_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .. import service, styles
from ..config import get_config
from ..contract import AgentChatRequest, AgentChatResponse, AgentStep, Card, ProfileNotFoundError
from . import llm, prompts
from .tools import build_tools

_THINK = re.compile(r"<think>.*?</think>", re.S)
_memory = InMemorySaver()  # short-term memory (per thread), kept while the server runs


class LLMUnavailableError(RuntimeError):
    """503: the LLM server (Ollama) is not reachable or the model is not pulled."""


class CoachState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    profile: str


async def _system_prompt(profile: str) -> str:
    space = await styles.get_space()
    info = await service.styles_info()
    descriptions = {s.id: s.description for s in space.styles.styles}
    cat = prompts.catalogue(info.styles, info.families, descriptions)
    return prompts.SYSTEM.format(catalogue=cat, profile=profile)


def build_graph(user_id: str, checkpointer=None):
    tools = build_tools(user_id)
    window = get_config().agent.history_messages

    async def recall_profile(state: CoachState) -> dict:
        try:
            p = (await service.profile(state["user_id"])).model_dump(mode="json", exclude={"taste_vector"})
        except ProfileNotFoundError:
            p = None
        return {"profile": prompts.profile_text(p, (await styles.get_space()).labels())}

    async def coach(state: CoachState) -> dict:
        history = trim_messages(
            state["messages"],
            max_tokens=window,
            token_counter=len,  # counts messages, not tokens
            strategy="last",
            start_on=["human", "ai"],  # never starts on a tool result cut from its call
        )
        msgs = [SystemMessage(await _system_prompt(state["profile"])), *history]
        return {"messages": [_dedupe_calls(await llm.get_model().bind_tools(tools).ainvoke(msgs))]}

    g = StateGraph(CoachState)
    g.add_node("recall_profile", recall_profile)
    g.add_node("coach", coach)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "recall_profile")
    g.add_edge("recall_profile", "coach")
    g.add_conditional_edges("coach", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "recall_profile")
    return g.compile(checkpointer=checkpointer)


def _dedupe_calls(msg: AIMessage) -> AIMessage:
    """Small models sometimes repeat the same tool call in one message: run it once (an update must not
    be applied twice)."""
    if not getattr(msg, "tool_calls", None):
        return msg
    seen, calls = set(), []
    for c in msg.tool_calls:
        key = (c["name"], repr(sorted(c["args"].items())))
        if key not in seen:
            seen.add(key)
            calls.append(c)
    return msg if len(calls) == len(msg.tool_calls) else msg.model_copy(update={"tool_calls": calls})


def _short(text: str, n: int = 400) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


async def chat(req: AgentChatRequest) -> AgentChatResponse:
    t0 = time.perf_counter()
    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    config = {
        "configurable": {"thread_id": f"{req.user_id}:{thread_id}"},
        "recursion_limit": get_config().agent.max_steps,
    }
    graph = build_graph(req.user_id, _memory)
    seen = len((await graph.aget_state(config)).values.get("messages", []))
    try:
        state = await graph.ainvoke({"messages": [HumanMessage(req.message)], "user_id": req.user_id}, config)
        new = state["messages"][seen:]
    except GraphRecursionError:
        new = (await graph.aget_state(config)).values.get("messages", [])[seen:]
        new.append(AIMessage("Désolé, je n'ai pas réussi à terminer. Reformulez votre demande ?"))
    except Exception as e:  # connection refused, model not pulled...
        if _is_llm_error(e):
            raise LLMUnavailableError(f"LLM unavailable ({llm.model_name()}): {e}") from e
        raise

    results = {m.tool_call_id: m for m in new if isinstance(m, ToolMessage)}
    steps, cards, changed = [], [], False
    for m in new:
        for call in getattr(m, "tool_calls", None) or []:
            res = results.get(call["id"])
            content = str(res.content) if res else ""
            steps.append(AgentStep(tool=call["name"], args=call["args"], result=_short(content)))
            if call["name"] == "recommend_outfits" and res is not None and res.artifact:
                cards = [Card.model_validate(c) for c in res.artifact]
            if call["name"] == "update_style_preferences" and content.startswith("Applied"):
                changed = True
    reply = next((m for m in reversed(new) if isinstance(m, AIMessage) and not m.tool_calls), None)
    text = _THINK.sub("", str(reply.content)).strip() if reply else ""
    return AgentChatResponse(
        user_id=req.user_id,
        thread_id=thread_id,
        reply=text or "…",
        steps=steps,
        cards=cards,
        profile_changed=changed,
        model=llm.model_name(),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def _is_llm_error(e: Exception) -> bool:
    import httpx

    try:
        from ollama import ResponseError
    except ImportError:  # ollama not installed (provider: shared)
        ResponseError = ()  # noqa: N806
    return isinstance(e, (httpx.ConnectError, ConnectionError, ResponseError))
