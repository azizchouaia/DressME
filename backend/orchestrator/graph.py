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


ASK_PIECE = ("Happy to judge it against your wardrobe! Which piece is it? Send me a photo, or tell me the type, "
             "the colour and the price, for example: \"a navy blazer at 120 TND\".")


def route_by_rules(text: str, tool_names: set, attachment: dict | None = None, pending: dict | None = None,
                   memory: dict | None = None) -> dict | None:
    """Deterministic routing for clear requests, with typos, French and Tounsi (orchestrator/understand.py).
    -> {"name", "args", "memory"} to call an agent, {"ask": text, "intent": {...}} to ask first, or None (the LLM).
    memory = the last request ({agent, piece, text}): follow-ups like "and in black?", "cheaper?",
    "for tomorrow instead?" reuse it."""
    from .understand import followup, intent_of, piece_of

    intent = intent_of(text)
    piece = piece_of(text)
    att = attachment or {}
    mem = memory or {}
    if mem.get("agent") and not att.get("image"):
        follow = followup(text, intent, piece, mem)
        if follow:
            intent, piece, text = follow
    if pending and pending.get("tool") == "smartbuy" and intent in (None, "smartbuy") and (piece["type"] or att.get("image")):
        intent = "smartbuy"  # the answer to "which piece is it?"
        piece = {**piece, "price": piece["price"] or pending.get("price")}
    if not intent and att.get("image"):
        intent = "smartbuy"  # a photo alone: "what do you think of this piece?"
    intent = {"laundry": "stylist"}.get(intent, intent)
    if intent == "gaps":
        return {"gaps": True}
    if not intent or intent not in tool_names:
        return None
    if intent == "smartbuy":
        if not piece["type"] and not att.get("image"):
            return {"ask": ASK_PIECE, "intent": {"tool": "smartbuy", "price": piece["price"]}}
        probe = att.get("probe") or att.get("image") or f"custom:{piece['type']}:{piece['colour'] or 'black'}"
        args: dict = {"probe_image": probe}
        if piece["price"]:
            args["price_tnd"] = piece["price"]
        return {"name": "smartbuy", "args": args, "memory": {"agent": "smartbuy", "piece": piece, "text": text}}
    return {"name": intent, "args": args_for(intent, text, piece),
            "memory": {"agent": intent, "piece": piece, "text": text}}


def args_for(agent: str, text: str, piece: dict) -> dict:
    """The arguments each agent's own schema expects (orchestrator/registry: one schema per tool)."""
    from .replies import city_of

    if agent == "localshop":
        a: dict = {"query": text}
        if piece.get("type"):
            a["subcategory"] = piece["type"]
        if piece.get("colour"):
            a["color"] = piece["colour"]
        if piece.get("price"):
            a["max_price_tnd"] = piece["price"]
        if city := city_of(text):
            a["city"] = city
        return a
    if agent == "challenges":
        return {"action": "recommend"}
    if agent == "talk":
        return {"message": text}
    if agent in ("stylist", "tryon"):
        return {"action": "chat", "payload": {"message": text}}
    return {"message": text, "payload": {"message": text}}  # wardrobe, profile, trips, taste


def agent_error_reply(agent: str, error: str) -> str:
    """What the user reads when an agent could not finish: what to do next, no stack trace."""
    hints = {
        "smartbuy": "Send me a photo of the piece, or its type, colour and price (\"a black jacket at 200 TND\").",
        "stylist": "Add at least a top, a bottom and shoes in your Wardrobe, then ask me again.",
        "localshop": "Tell me the piece and the city, for example \"a white shirt in Tunis under 80 TND\".",
        "wardrobe": "Check that the database is running, then open Wardrobe to add pieces.",
        "tryon": "Open My 3D avatar from Outfits to try pieces on.",
    }
    detail = error.split(":", 2)[-1].strip()[:140]
    return (f"I couldn't finish that with the {agent or 'right'} agent ({detail}). "
            + hints.get(agent, "Could you say it another way, or give me a bit more detail?"))


def _friendly_tool_error(e: Exception) -> str:
    """An agent failed: the writer turns it into a helpful sentence (never a 503 for the user)."""
    return f"AGENT_ERROR: {type(e).__name__}: {e}"


def build_graph(model=None, tools=None, checkpointer=None, rules=None):
    """Compile the graph. Tests pass a scripted model and a stand-in tool."""

    chosen = list(get_tools() if tools is None else tools)
    use_rules = (tools is None) if rules is None else rules  # the app: rules first; unit tests: the scripted model
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
            pending = state.get("pending")
            if pending:  # a new, clear request is not an answer to the open question
                from .understand import intent_of

                text = last.content if isinstance(last.content, str) else str(last.content)
                from .replies import yes_no

                new = intent_of(text)
                if new and (new != pending.get("agent") or (len(text.split()) >= 4 and yes_no(text) is None)):
                    pending = None
            return {"tool_calls": 0, "pending_question": None, "pending": None, "answering": pending}
        return {}

    async def planner(state: ChatState):
        if not int(state.get("tool_calls") or 0) and not state.get("answering") and use_rules:
            last = state["messages"][-1]
            if isinstance(last, HumanMessage):
                text = last.content if isinstance(last.content, str) else str(last.content)
                from .replies import small_talk

                from .replies import OUT_OF_SCOPE, off_topic

                chat = small_talk(text) if not state.get("attachment") else None
                if not chat and not state.get("attachment") and off_topic(text):
                    chat = OUT_OF_SCOPE
                if chat:
                    return {"messages": [AIMessage(content=chat, additional_kwargs={"final": True})], "intent": None}
                hit = route_by_rules(text, {getattr(t, "name", None) for t in chosen}, state.get("attachment"),
                                     state.get("intent"), state.get("memory"))
                if hit and hit.get("gaps"):  # what is missing in my wardrobe: computed from M1, no LLM
                    from shared.wardrobe_gaps import user_gaps

                    from .replies import gaps_reply

                    from .replies import occasion_gaps

                    found = occasion_gaps(user_gaps(state.get("user_id"), k=11), text)
                    mem = {"agent": "localshop", "piece": {"type": found[0]["piece"].split(" ", 1)[1],
                                                           "colour": found[0]["piece"].split(" ", 1)[0], "price": None},
                           "text": f"find {found[0]['piece']}"} if found and found[0]["piece"] else None
                    return {"messages": [AIMessage(content=gaps_reply(found), additional_kwargs={"final": True})],
                            "memory": mem, "cards": [{"gaps": [g for g in found if g["piece"]]}] if found else []}
                if hit and "ask" in hit:  # a clear intent but a missing detail: ask, remember the intent
                    return {"messages": [AIMessage(content=hit["ask"], additional_kwargs={"final": True})],
                            "intent": hit["intent"]}
                if hit:
                    log.info("rule route -> %s", hit["name"])
                    call = {"name": hit["name"], "args": hit["args"]}
                    return {"intent": None, "memory": hit.get("memory"),
                            "messages": [AIMessage(content="", tool_calls=[{**call, "id": f"call_{uuid.uuid4().hex[:8]}",
                                                                            "type": "tool_call"}])]}
        answering = state.get("answering")
        if use_rules and answering and not int(state.get("tool_calls") or 0) and answering.get("question_key"):
            # the user answers an agent's question: send it back to that agent, with the key it asked for
            from .replies import yes_no

            last = state["messages"][-1]
            text = last.content if isinstance(last.content, str) else str(last.content)
            yn = yes_no(text)
            value = yn if yn is not None else text
            args = {"session_id": state.get("session_id") or "",
                    "answer": {"question_key": answering["question_key"], "value": value}}
            return {"messages": [AIMessage(content="", tool_calls=[{"name": answering["agent"], "args": args,
                                                                     "id": f"call_{uuid.uuid4().hex[:8]}",
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
            if call["name"] == "localshop" and not args.get("answer"):
                from .replies import account_of

                acc = account_of(user_id)
                if not args.get("gender") and acc.get("gender") in ("female", "male"):
                    args["gender"] = {"female": "women", "male": "men"}[acc["gender"]]
                args.setdefault("language", "en")
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
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.additional_kwargs.get("final"):
            return {}  # already the answer (a question the rules asked)
        if isinstance(last, ToolMessage) and "AGENT_ERROR" in str(last.content):
            return {"messages": [AIMessage(content=agent_error_reply(getattr(last, "name", "") or "", str(last.content)))]}
        turn = _this_turn(state["messages"])
        payload = last_payload(turn) or {}
        if use_rules:
            from .replies import from_facts

            fixed = from_facts(tool_name(turn), payload)
            if fixed:
                return {"messages": [AIMessage(content=fixed)]}
        user_text = next((m.content for m in turn if isinstance(m, HumanMessage)), "")
        user_text = user_text if isinstance(user_text, str) else str(user_text)
        no_agent = not any(isinstance(m, ToolMessage) for m in turn)
        if no_agent and use_rules:
            from .replies import GENERAL_PROMPT, guard

            history = [m for m in state["messages"] if isinstance(m, HumanMessage)
                       or (isinstance(m, AIMessage) and m.content and not m.tool_calls)][-6:]
            try:
                draft = await brain.ainvoke([("system", GENERAL_PROMPT), *history])
                text = draft.content if isinstance(draft.content, str) else ""
            except Exception:  # noqa: BLE001 - LLM down: the guard answers
                text = ""
            return {"messages": [AIMessage(content=guard(text, user_text))]}
        system = f"{WRITER_PROMPT}\nFacts:\n{json.dumps(protected_facts(payload), ensure_ascii=False)}"
        draft = await brain.ainvoke([("system", system), *state["messages"]])
        text = draft.content if isinstance(draft.content, str) else json.dumps(draft.content)
        text = enforce_facts(text, payload)
        if use_rules:
            from .replies import guard

            text = guard(text, user_text)
        return {"messages": [AIMessage(content=text)]}

    graph = StateGraph(ChatState)
    graph.add_node("begin", begin)
    graph.add_node("planner", planner)
    graph.add_node("prepare_tools", prepare_tools)
    graph.add_node("tools", ToolNode(chosen, handle_tool_errors=_friendly_tool_error))
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
        "trace": trace_of(message, _this_turn(out.get("messages") or []), out.get("cards") or []),
    }


AGENT_NAMES = {"smartbuy": "Smart Buy (BO5)", "stylist": "Stylist (BO2)", "localshop": "Local shops (BO6)",
               "wardrobe": "Wardrobe (M1)", "profile": "Style profile (M5)", "taste": "Taste (M5)",
               "challenges": "Challenges (BO7)", "tryon": "Try-on (BO9)", "share": "Share (BO7)", "trips": "Trips",
               "talk": "Talk"}


def _short(d: dict, keys: int = 4) -> str:
    parts = []
    for k, v in (d or {}).items():
        if k in ("user_id", "session_id") or v in (None, "", {}, []):
            continue
        if isinstance(v, dict):
            v = _short(v, 3)
        parts.append(f"{k}: {str(v)[:40]}")
        if len(parts) >= keys:
            break
    return ", ".join(parts)


def trace_of(message: str, turn: list, cards: list) -> list[dict]:
    """The workflow of one turn, for the app: understood -> routed -> agent answered -> reply written."""
    from .understand import intent_of, piece_of

    first = message.split("\n", 1)[0]
    intent, piece = intent_of(first), {k: v for k, v in piece_of(first).items() if v}
    steps = [{"step": "understand", "title": "Orchestrator understood",
              "detail": (f"intent: {intent}" if intent else "no clear intent (free question)")
              + (f" · {_short(piece)}" if piece else "")}]
    used = False
    for m in turn:
        if isinstance(m, AIMessage) and m.tool_calls:
            for c in m.tool_calls:
                name = c.get("name")
                steps.append({"step": "route", "agent": name, "title": f"Asked {AGENT_NAMES.get(name, name)}",
                              "detail": _short(c.get("args") or {})})
        elif isinstance(m, ToolMessage):
            used = True
            body = m.content
            try:
                body = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                pass
            failed = getattr(m, "status", "") == "error" or (isinstance(body, dict) and bool(body.get("error")))
            res = body.get("result") if isinstance(body, dict) and isinstance(body.get("result"), dict) else body
            detail = ""
            if isinstance(res, dict):
                detail = _short({k: res.get(k) for k in ("verdict", "score", "question")})
                for k in ("outfits", "items", "results", "challenges"):
                    if isinstance(res.get(k), list):
                        detail = (detail + ", " if detail else "") + f"{len(res[k])} {k}"
            steps.append({"step": "agent", "agent": m.name, "ok": not failed,
                          "title": f"{AGENT_NAMES.get(m.name, m.name)} {'failed' if failed else 'answered'}",
                          "detail": detail or ("error handled kindly" if failed else "done")})
    gaps = next((c["gaps"] for c in cards if isinstance(c, dict) and "gaps" in c), None)
    if gaps is not None:
        used = True
        steps.append({"step": "agent", "agent": "gaps", "ok": True, "title": "Wardrobe gaps checked (M1)",
                      "detail": f"{len(gaps)} missing essentials"})
    last = next((m for m in reversed(turn) if isinstance(m, AIMessage) and not m.tool_calls), None)
    rules = bool(last and last.additional_kwargs.get("final"))
    steps.append({"step": "reply", "title": "Reply written",
                  "detail": "from the agent's facts" if used else ("by the rules (no LLM)" if rules else "by the LLM")})
    return steps


def _this_turn(messages: list) -> list:
    """The messages after the user's last message (an older agent result must not answer this turn)."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i:]
    return messages


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
