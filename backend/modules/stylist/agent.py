"""Stylist agent (BO1 personalised recommendations + BO2 time optimisation): an LLM agent that answers in
natural language and uses the module agents M2 / M3 / M4 / M9 / M17 as its tools.

Pipeline of one message:
  1. memory      load the conversation (short-term) + the user's taste profile (long-term)
  2. retrieval   RAG: the wardrobe pieces closest to the request (FashionCLIP), pieces in the laundry,
  last worn
  3. prompt      system prompt (role, rules, few-shot example) + retrieved context + conversation
  4. reasoning   local LLM (Ollama, Qwen2.5) picks tools; each tool call is validated, executed through the
                 agent bus, its result fed back; up to MAX_STEPS rounds
  5. answer      LLM writes the reply in the user's language; structured outfits / avatar for other agents
  6. memory      the turn is saved
Every step is recorded in `trace` (shown on the demo page: the agent's pipeline, live).
"""

from __future__ import annotations

import json
import re
import time
from typing import ClassVar

from pydantic import BaseModel

from shared.action_agent import Action, ActionAgent

from . import llm, memory, tools

MAX_STEPS = 4
PREF_WORDS = re.compile(
    r"\b(i (really )?(don'?t|do not) like|i hate|i love|i like|i prefer|j'?aime|je d[ée]teste|je "
    r"pr[ée]f[èe]re)\b",
    re.I,
)
OUTFIT_WORDS = re.compile(
    r"\b(wear|outfit|dress me|what "
    r"should|porte|portes|porter|mettre|mets|tenue|habiller|look|ilbes|nalbes|نلبس|لبس)\b",
    re.I,
)

SYSTEM = """You are DressMe Stylist, a personal fashion assistant for a user in Tunisia.
You plan outfits from the user's OWN wardrobe and help them save time every morning.

Rules:
- Use the tools to get facts. Never invent pieces: only use pieces returned by the tools.
- For "what should I wear" questions: call day_context (when a day is mentioned), then recommend_outfits.
- Pieces in the laundry are excluded automatically.
- When the user states a taste ("I hate yellow", "I love oversize"), call remember_preference.
- Answer in the user's language (English, French or Tunisian Arabic), in 2 to 4 short sentences.

Example of the steps (the piece names come from the tools, never from this example):
User: what do I wear tomorrow for work?
-> call day_context(day="tomorrow"), then recommend_outfits(occasion="work", day="tomorrow")
-> answer with the pieces of outfit 1 returned by recommend_outfits."""

ANSWER = """You are DressMe Stylist, talking directly to the user. Use FACTS only.
Start with the outfit, like: "Wear your <pieces of outfit 1>." (use the exact piece names from FACTS).
Then one sentence on why it fits (occasion, weather, mood from FACTS). You may end with outfit 2 as a backup.
Never name a piece that is not in FACTS. 2 to 4 short sentences."""

FRENCH = re.compile(
    r"\b(je|tu|quoi|qu'est|porte|aujourd'hui|demain|mets|tenue|pour|avec|merci|bonjour)\b", re.I
)


LAUNDRY_WORDS = re.compile(r"\b(laundry|wash|dirty|lessive|linge|sale|machine|clean|propre)\b", re.I)
BACK_WORDS = re.compile(r"\b(back|clean|propre|ready|sorti|done)\b", re.I)
WORN_WORDS = re.compile(r"\b(i wore|i'?m wearing|j'?ai port[ée]|je porte aujourd'?hui|lbest)\b", re.I)


def guard_call(message: str) -> dict | None:
    """The tool a request needs when the model did not call one (keyword rules, checked in this order)."""
    if LAUNDRY_WORDS.search(message):
        status = "available" if BACK_WORDS.search(message) else "laundry"
        return {"name": "set_laundry", "arguments": {"pieces": message, "status": status}}
    if WORN_WORDS.search(message):
        return {"name": "log_worn", "arguments": {"pieces": message}}
    if OUTFIT_WORDS.search(message):
        return {"name": "recommend_outfits", "arguments": {}}
    return None


def language(text: str) -> str:
    if re.search(r"[\u0600-\u06FF]", text):
        return "Tunisian Arabic"
    return "French" if FRENCH.search(text) else "English"


class ChatPayload(BaseModel):
    message: str
    session_id: str = "default"
    show_on_avatar: bool = False  # also put the best outfit on the 3D avatar


class ChatRequest(BaseModel):
    user_id: str | None = None
    payload: ChatPayload


class _Req(BaseModel):
    user_id: str | None = None
    payload: dict = {}


async def chat(user: str, p: ChatPayload) -> dict:
    trace = []

    def step(name: str, t0: float, **detail):
        trace.append({"step": name, "ms": int((time.perf_counter() - t0) * 1000), **detail})

    # 1. memory
    t = time.perf_counter()
    prof = memory.profile(user)
    hist = memory.recent(user, p.session_id)
    step("memory", t, turns=len(hist), profile=prof)

    # 2. retrieval (RAG)
    t = time.perf_counter()
    cat = await tools.catalog(user)
    box = tools.Toolbox(user, cat)
    relevant = tools.retrieve(p.message, cat["items"])
    unavailable = (await box.t_unavailable_pieces({}))["unavailable"]
    step(
        "retrieval",
        t,
        wardrobe=cat["source"],
        pieces=len(cat["items"]),
        relevant=[r["name"] for r in relevant],
        unavailable=unavailable,
    )

    # 3. prompt
    context = {
        "wardrobe_source": cat["source"],
        "relevant_pieces": [r["name"] for r in relevant],
        "unavailable_now": unavailable,
        "user_preferences": prof,
    }
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "system", "content": "CONTEXT: " + json.dumps(context, ensure_ascii=False)},
        *hist,
        {"role": "user", "content": p.message + f"\n\n(Answer in {language(p.message)}.)"},
    ]

    # 4. reasoning: tool loop
    called = []
    reply = ""
    for i in range(MAX_STEPS):
        t = time.perf_counter()
        msg = llm.chat(messages, tools.ollama_tools())
        calls = msg.get("tool_calls") or []
        forced = guard_call(p.message) if not calls and i == 0 else None
        if forced:
            # guard for a small model answering from imagination: actions and outfit questions always go
            # through the real tool (never "done" without doing it)
            calls = [{"function": forced}]
            step("llm", t, decision=f"guard: -> {forced['name']}")
        else:
            step("llm", t, decision=[c["function"]["name"] for c in calls] or "answer")
        if not calls:
            reply = msg.get("content", "")
            break
        messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls})
        for c in calls:
            name, args = c["function"]["name"], c["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            t = time.perf_counter()
            out = await box.call(name, args)
            called.append(name)
            step("tool", t, tool=name, args=args, result=out)
            messages.append(
                {"role": "tool", "content": json.dumps(out, ensure_ascii=False, default=str)[:3000]}
            )
    # safety net (small model): a stated taste is always saved
    if PREF_WORDS.search(p.message) and "remember_preference" not in called:
        t = time.perf_counter()
        ext = llm.chat(
            [
                {
                    "role": "system",
                    "content": "Extract the clothing preference stated by the user as JSON "
                    '{"kind": "likes" or "dislikes", "value": "short phrase, e.g. yellow"}. If none, '
                    '{"kind": "none", "value": ""}.',
                },
                {"role": "user", "content": p.message},
            ],
            fmt="json",
        )
        try:
            pref = json.loads(ext.get("content") or "{}")
        except ValueError:
            pref = {}
        if pref.get("kind") in ("likes", "dislikes") and pref.get("value"):
            out = await box.call("remember_preference", pref)
            called.append("remember_preference")
            step(
                "tool",
                t,
                tool="remember_preference",
                args=pref,
                result=out,
                note="guard: preference extraction",
            )
    # grounding: when outfits were found, the final answer is written from those exact pieces only
    if box.outfits:
        facts = {
            "context": box.context,
            "outfits": [
                {"n": i + 1, "pieces": [x["name"] for x in o["items"]], "why": o["why"]}
                for i, o in enumerate(box.outfits[:2])
            ],
            "unavailable_now": unavailable,
            "user_preferences": memory.profile(user),
        }
        t = time.perf_counter()
        reply = llm.chat(
            [
                {"role": "system", "content": ANSWER + f"\nWrite in {language(p.message)}."},
                {
                    "role": "system",
                    "content": "FACTS: "
                    + json.dumps(facts, ensure_ascii=False)
                    + " (the 'why' texts are notes for you, rephrase them).",
                },
                *hist,
                # the language order goes last: small models follow the last instruction best
                {"role": "user", "content": p.message + f"\n\n(Answer in {language(p.message)}.)"},
            ]
        ).get("content", reply)
        step("llm", t, decision="grounded answer from tool results")
        reply = reply or ""
    if not reply:  # tool budget used: ask for the final answer without tools
        t = time.perf_counter()
        reply = llm.chat(messages).get("content", "")
        step("llm", t, decision="answer")

    # 5. structured result for other agents (+ optional avatar)
    if p.show_on_avatar and box.outfits and box.avatar is None:
        await box.t_show_on_avatar({})
    # 6. memory
    memory.append(user, p.session_id, "user", p.message)
    memory.append(user, p.session_id, "assistant", reply)
    return {
        "result": {
            "reply": reply,
            "outfits": box.outfits,
            "avatar": box.avatar,
            "context": box.context,
            "tools_used": called,
            "model": llm.MODEL,
            "trace": trace,
        },
        "mocked": False,
    }


class StylistAgent(ActionAgent):
    name = "stylist"
    description = (
        "DressMe Stylist (BO1 / BO2): LLM agent that answers fashion requests in natural language from the "
        "user's own wardrobe: what to wear for a day / occasion / weather, complete an outfit, laundry, worn "
        "log, forgotten pieces, capsule wardrobe, show an outfit on the 3D avatar; remembers the user's "
        "taste. "
        "Send {action: 'chat', payload: {message}}; returns reply + structured outfits."
    )
    depends_on: ClassVar[tuple[str, ...]] = (
        "m02_recommendation",
        "m03_wear_log",
        "m04_scheduler",
        "m09_avatar_3d",
        "m17_capsule",
    )

    def actions(self) -> dict[str, Action]:
        import asyncio

        def _chat(req: dict) -> dict:
            p = ChatPayload.model_validate(req["payload"])
            return asyncio.run(chat(memory._safe(req.get("user_id"), "anonymous"), p))

        def _memory(req: dict) -> dict:
            u = memory._safe(req.get("user_id"), "anonymous")
            s = (req.get("payload") or {}).get("session_id", "default")
            return {"result": {"profile": memory.profile(u), "history": memory.history(u, s)}}

        def _forget(req: dict) -> dict:
            u = memory._safe(req.get("user_id"), "anonymous")
            memory.forget(u, (req.get("payload") or {}).get("session_id"))
            return {"result": {"forgotten": True}}

        return {
            "chat": Action("a message in natural language -> reply + outfits (+ avatar)", _chat, ChatRequest),
            "memory": Action("what the stylist remembers: taste profile + conversation", _memory, _Req),
            "forget": Action("erase the conversation (session_id) or everything", _forget, _Req),
            "status": Action("is the local LLM running", lambda req: {"result": llm.available()}, _Req),
        }


agent = StylistAgent()
