"""LangGraph orchestrator for BO8.

The planner picks an agent and fills its arguments. The agent's tool decides
the facts. This graph only asks the agent's question, chains next_actions, and
words the reply without changing a verdict, score, price, or size.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .prompts import SYSTEM_PROMPT, WRITER_PROMPT
from .registry import get_tools
from .state import ChatState

log = logging.getLogger("dressme.orchestrator")

MAX_TOOL_CALLS = 3
PROTECTED = (
    "verdict",
    "score",
    "price",
    "price_tnd",
    "size",
    "cost_per_outfit_tnd",
    "cost_per_wear_tnd",
)


def _rescue_text_call(reply, tools, messages):
    """Small local models (llama3.1 on Ollama) sometimes WRITE the tool call as JSON text instead of
    making it. Turn that text back into a real tool call so the user never sees raw JSON."""
    import json
    import re
    import uuid

    text = (getattr(reply, "content", "") or "").strip()
    if getattr(reply, "tool_calls", None):
        return reply
    names = {getattr(t, "name", None) for t in tools or []} - {None}
    m = re.search(r'"name"\s*:\s*"([^"]+)"', text)
    if not m or m.group(1) not in names:
        # other shapes of a written call: stylist(action="chat", ...)  /  "the function to use is `stylist`"
        alts = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        m = re.search(rf"\b({alts})\s*\(", text) if alts else None
        if not m and alts and re.search(r"function|tool|call|action", text, re.I):
            m = re.search(rf"`({alts})`", text)
        if not m:
            return reply
        last_user = next((x.content for x in reversed(messages) if getattr(x, "type", "") == "human"), "")
        a = re.search(r'action\s*[=:]\s*["\']([a-z_]+)["\']', text)
        return AIMessage(content="", tool_calls=[{"name": m.group(1),
                                                  "args": {"action": a.group(1) if a else "chat",
                                                           "payload": {"message": last_user}},
                                                  "id": f"call_{uuid.uuid4().hex[:8]}", "type": "tool_call"}],
                         id=getattr(reply, "id", None))
    args: dict = {}
    start, end = text.find("{"), text.rfind("}")  # the JSON may be wrapped in prose or a ``` block
    text = text[start:end + 1] if 0 <= start < end else text
    try:
        data = json.loads(text)
        args = data.get("parameters") or data.get("arguments") or {}
        if isinstance(args.get("payload"), str):
            args["payload"] = json.loads(args["payload"])
    except Exception:  # noqa: BLE001 - broken JSON: keep what we can read
        a = re.search(r'"action"\s*:\s*"([^"]+)"', text)
        args = {"action": a.group(1)} if a else {}
    if not isinstance(args.get("payload"), dict):
        last_user = next((x.content for x in reversed(messages) if getattr(x, "type", "") == "human"), "")
        args["payload"] = {"message": last_user}
    args.setdefault("action", "chat")
    return AIMessage(content="", tool_calls=[{"name": m.group(1), "args": args, "id": f"call_{uuid.uuid4().hex[:8]}",
                                              "type": "tool_call"}], id=getattr(reply, "id", None))


_TYPES = ["t-shirt", "shirt", "sweater", "blouse", "jeans", "chinos", "trousers", "skirt", "sneakers", "loafers",
          "boots", "sandals", "jacket", "coat", "blazer", "dress", "jebba"]
_COLOURS = ["white", "black", "grey", "navy", "beige", "brown", "camel", "blue", "olive", "red", "pink", "green",
            "burgundy", "mustard"]
_RULES = [  # (tool, words): a clear request goes straight to its agent, the LLM only for the rest
    ("smartbuy", r"\b(should i (buy|get)|worth (it|buying)|buy (it|this|a|an)|ach[eè]ter|nechri|n?chri)\b"),
    ("localshop", r"\b(find .* (in|at) (a )?(shop|store)|where (can|to) (i )?buy|in a shop|local shops?|boutique|magasin)\b"),
    ("challenges", r"\b(challenges?|d[ée]fis?)\b"),
    ("wardrobe", r"\b(show|list|what('s| is) in) my (wardrobe|closet|clothes)\b|\bgarde-robe\b"),
    ("stylist", r"\b(what (should|do|can) i wear|outfit|tenue|n?elbes|look for (today|tomorrow))\b"),
]


def route_by_rules(text: str, tool_names: set, attachment: dict | None = None) -> dict | None:
    """Deterministic routing for clear requests (the 8B local model often mis-routes or writes the call)."""
    low = (text or "").lower()
    for name, rx in _RULES:
        if name not in tool_names or not re.search(rx, low):
            continue
        if name == "smartbuy":
            typ = next((t for t in _TYPES if re.search(rf"\b{re.escape(t)}s?\b", low)), None)
            col = next((k for k in _COLOURS if re.search(rf"\b{k}\b", low)), None)
            if not typ and not (attachment or {}).get("image"):
                continue  # nothing to judge: let the LLM ask
            args: dict = {"probe_image": (attachment or {}).get("probe") or f"custom:{typ}:{col or 'black'}"}
            price = re.search(r"(\d+(?:[.,]\d+)?)\s*(tnd|dt|dinars?)", low)
            if price:
                args["price_tnd"] = float(price.group(1).replace(",", "."))
            return {"name": name, "args": args}
        return {"name": name, "args": {"action": "chat", "message": text, "payload": {"message": text}}}
    return None


def build_graph(model=None, tools=None, checkpointer=None):
    """Compile the graph. Tests pass a scripted model and a stand-in tool."""

    chosen = list(get_tools() if tools is None else tools)
    if model is None:
        from shared.llm import get_chat_model

        brain = get_chat_model()
    else:
        brain = model
    planner_llm = brain.bind_tools(chosen) if chosen and hasattr(brain, "bind_tools") else brain

    async def begin(state: ChatState):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            # an open question from the last turn: this message is its answer
            return {"tool_calls": 0, "pending_question": None, "pending": None,
                    "answering": state.get("pending")}
        return {}

    async def planner(state: ChatState):
        if not int(state.get("tool_calls") or 0) and not state.get("answering") and tools is None:
            last = state["messages"][-1]
            if isinstance(last, HumanMessage):
                text = last.content if isinstance(last.content, str) else str(last.content)
                hit = route_by_rules(text, {getattr(t, "name", None) for t in chosen}, state.get("attachment"))
                if hit:
                    log.info("rule route -> %s", hit["name"])
                    return {"messages": [AIMessage(content="", tool_calls=[{**hit, "id": f"call_{uuid.uuid4().hex[:8]}",
                                                                            "type": "tool_call"}])]}
        system = (
            f"{SYSTEM_PROMPT}\n"
            f"session_id: {state.get('session_id', '')}\n"
            f"user_id: {state.get('user_id', '')}"
        )
        answering = state.get("answering")
        if answering and not int(state.get("tool_calls") or 0):
            key = answering.get("question_key")
            system += (
                f"\nThe user's last message answers the question of the agent '{answering['agent']}': "
                f"\"{answering['question']}\". Call '{answering['agent']}' again with the same session_id"
                + (f" and answer={{\"question_key\": \"{key}\", \"value\": <the user's answer>}}." if key
                   else " and pass the user's answer.")
            )
        reply = await planner_llm.ainvoke([("system", system), *state["messages"]])
        return {"messages": [_rescue_text_call(reply, chosen, state["messages"])]}

    def prepare_tools(state: ChatState, config):
        configurable = (config or {}).get("configurable") or {}
        user_id = state.get("user_id") or "demo"
        session_id = state.get("session_id") or configurable.get("thread_id") or ""
        last = state["messages"][-1]
        calls = []
        att = state.get("attachment") or {}
        for call in last.tool_calls:
            args = dict(call.get("args") or {})
            args.setdefault("user_id", user_id)
            args.setdefault("session_id", session_id)
            if att.get("image"):  # the photo sent with the message goes to the agent that reads photos
                if call["name"] == "smartbuy" and not args.get("answer"):
                    args["probe_image"] = att.get("probe") or att["image"]
                else:
                    payload = dict(args.get("payload") or {})
                    payload.setdefault("image", att["image"])
                    if att.get("label"):
                        payload.setdefault("query", att["label"])
                    args["payload"] = payload
            calls.append({"name": call["name"], "args": args, "id": call["id"], "type": "tool_call"})
        return {"messages": [AIMessage(content=last.content or "", tool_calls=calls, id=last.id)]}

    def after_tool(state: ChatState):
        payload = last_payload(state["messages"])
        calls = int(state.get("tool_calls") or 0) + 1
        name = tool_name(state["messages"])
        log.info("session=%s tool=%s call=%s", state.get("session_id"), name, calls)
        cards = list(state.get("cards") or [])
        if payload is not None:
            cards.append(payload)
        update: dict[str, Any] = {"tool_calls": calls, "cards": cards, "last_agent": name}
        question = (payload or {}).get("question")
        if isinstance(question, str) and question.strip():
            update["pending_question"] = question.strip()
            update["pending"] = {"agent": name, "question": question.strip(),
                                 "question_key": (payload or {}).get("question_key")}
        return update

    def route_after(state: ChatState):
        if state.get("pending_question"):
            return "ask_user"
        if int(state.get("tool_calls") or 0) >= MAX_TOOL_CALLS:
            return "writer"
        payload = last_payload(state["messages"]) or {}
        # chain only the steps an agent marks auto; the others are offered to the user as buttons
        if any(isinstance(a, dict) and a.get("auto") for a in payload.get("next_actions") or []):
            return "planner"
        return "writer"

    def ask_user(state: ChatState):
        return {"messages": [AIMessage(content=state.get("pending_question") or "")]}

    async def writer(state: ChatState):
        payload = last_payload(state["messages"]) or {}
        system = f"{WRITER_PROMPT}\nFacts:\n{json.dumps(protected_facts(payload), ensure_ascii=False)}"
        draft = await brain.ainvoke([("system", system), *state["messages"]])
        text = draft.content if isinstance(draft.content, str) else json.dumps(draft.content)
        return {"messages": [AIMessage(content=enforce_facts(text, payload))]}

    graph = StateGraph(ChatState)
    graph.add_node("begin", begin)
    graph.add_node("planner", planner)
    graph.add_node("prepare_tools", prepare_tools)
    graph.add_node("tools", ToolNode(chosen))
    graph.add_node("after_tool", after_tool)
    graph.add_node("ask_user", ask_user)
    graph.add_node("writer", writer)
    graph.set_entry_point("begin")
    graph.add_edge("begin", "planner")
    if chosen:
        graph.add_conditional_edges("planner", tools_condition, {"tools": "prepare_tools", END: "writer"})
    else:
        graph.add_edge("planner", "writer")
    graph.add_edge("prepare_tools", "tools")
    graph.add_edge("tools", "after_tool")
    graph.add_conditional_edges(
        "after_tool",
        route_after,
        {"ask_user": "ask_user", "planner": "planner", "writer": "writer"},
    )
    graph.add_edge("ask_user", END)
    graph.add_edge("writer", END)
    if checkpointer is False:
        return graph.compile()
    memory = MemorySaver() if checkpointer is None else checkpointer
    return graph.compile(checkpointer=memory)


async def run_turn(graph, *, user_id: str, session_id: str, message: str, attachment: dict | None = None) -> dict:
    """One user message. The same session_id keeps the open question and the history."""

    config = {"configurable": {"thread_id": session_id}}
    out = await graph.ainvoke(
        {
            "user_id": user_id,
            "session_id": session_id,
            "messages": [HumanMessage(content=message)],
            "tool_calls": 0,
            "pending_question": None,
            "cards": [],  # only this turn's agent results go back to the app
            "attachment": attachment,
        },
        config,
    )
    reply = ""
    for item in reversed(out.get("messages") or []):
        if isinstance(item, AIMessage) and item.content and not item.tool_calls:
            reply = item.content if isinstance(item.content, str) else str(item.content)
            break
    card = (out.get("cards") or [None])[-1] or {}
    return {
        "reply": reply,
        "question": out.get("pending_question"),
        "next_actions": card.get("next_actions") or [],
        "cards": out.get("cards") or [],
        "session_id": session_id,
        "last_agent": out.get("last_agent"),
    }


def last_payload(messages: list) -> dict | None:
    for item in reversed(messages):
        if not isinstance(item, ToolMessage):
            continue
        body = item.content
        if isinstance(body, dict):
            return body
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def tool_name(messages: list) -> str | None:
    for item in reversed(messages):
        if isinstance(item, ToolMessage):
            return item.name
    return None


def protected_facts(payload: dict) -> dict:
    facts = {}
    for key in PROTECTED:
        value = payload.get(key)
        if value is not None:
            facts[key] = value
    advice = payload.get("size_advice")
    if isinstance(advice, dict):
        if advice.get("size") is not None:
            facts["size"] = advice["size"]
        if advice.get("brand") is not None:
            facts["brand"] = advice["brand"]
    return facts


VERDICTS = {"buy", "think", "skip"}


def _number_forms(value: float) -> set[str]:
    forms = {str(value), f"{value:g}"}
    if float(value).is_integer():
        forms.add(str(int(value)))
    forms |= {f.replace(".", ",") for f in forms}
    return forms


def _has(reply: str, value) -> bool:
    low = reply.lower()
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return any(f in low for f in _number_forms(value))
    return str(value).lower() in low


def _contradicts(reply: str, facts: dict) -> bool:
    """The reply names another verdict than the agent's."""
    verdict = str(facts.get("verdict", "")).lower()
    if verdict not in VERDICTS:
        return False
    import re
    said = {v for v in VERDICTS if re.search(rf"\b{v}\b", reply.lower())}
    return bool(said - {verdict})


def enforce_facts(reply: str, payload: dict) -> str:
    """Keep the agent's facts. A reply that contradicts them is replaced; one that only misses some
    gets them added, so a good sentence is not thrown away."""

    facts = protected_facts(payload)
    if not facts:
        return reply
    if not _contradicts(reply, facts):
        missing = {k: v for k, v in facts.items() if not _has(reply, v)}
        if not missing:
            return reply
        if reply.strip():
            return reply.rstrip() + " (" + ", ".join(f"{k}: {v}" for k, v in missing.items()) + ")"
    parts = [f"{key}: {value}" for key, value in facts.items()]
    labels = [
        item.get("label") or item.get("tool")
        for item in payload.get("next_actions") or []
        if isinstance(item, dict)
    ]
    if any(labels):
        parts.append("next: " + ", ".join(label for label in labels if label))
    return ". ".join(parts) + "."
