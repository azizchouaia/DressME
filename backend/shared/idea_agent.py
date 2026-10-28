"""Idea agents: one agent per BO idea, each ruled by an LLM, all speaking the BO8 protocol.

    input  AgentCall   {user_id, session_id, language, message, payload}
    output AgentResult {agent, result, question, next_actions, mocked}

An idea agent has ACTIONS (its workflows). A call can name the action itself
(payload = {"action": "recommend", "args": {...}}: no LLM, for other agents), or only give a message: the
agent's LLM reads its own card and picks the action + arguments (JSON mode), runs the workflow (which calls
the module agents M2 / M3 / M4 / M7 / M9 / M17 as tools through the agent bus), then writes the answer from
the facts it got. Every step is recorded in result["steps"] (the agent's pipeline, shown on the demo page).

Memory (shared.agent_memory, per user):
  short-term   the conversation of a session + a session blackboard (last outfit, last day...) that every
               agent of the session reads and writes, so "swap the shoes" works after "what do I wear?"
  long-term    the user's taste profile (likes / dislikes / notes) used by every agent
  episodic     what was worn / washed lives in M3 and is read through the M3 agent
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from shared import agent_memory as memory
from shared import local_llm as llm
from shared.agent_card import AgentCall, AgentResult, describe
from shared.base_agent import BaseAgent

FRENCH = re.compile(
    r"\b(je|tu|quoi|qu'est|porte|aujourd'hui|demain|mets|tenue|pour|avec|merci|bonjour|mes)\b", re.I
)


def detect_language(text: str, given: str = "en") -> str:
    if re.search(r"[؀-ۿ]", text or ""):
        return "ar"
    if FRENCH.search(text or ""):
        return "fr"
    return given or "en"


LANG_NAME = {"en": "English", "fr": "French", "ar": "Tunisian Arabic"}

PREF_WORDS = re.compile(
    r"\b(i (really )?(don'?t|do not) like|i hate|i love|i like|i prefer|j'?aime|je d[ée]teste|je "
    r"pr[ée]f[èe]re)\b",
    re.I,
)


# ---------------- session blackboard (short-term memory shared by the agents of a session) ----------------
def _state_file(user: str, session: str):
    return memory._dir(user) / f"state_{memory._safe(session, 'default')}.json"


def get_state(user: str, session: str) -> dict:
    f = _state_file(user, session)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def update_state(user: str, session: str, **values) -> dict:
    s = get_state(user, session)
    s.update(values)
    _state_file(user, session).write_text(json.dumps(s, ensure_ascii=False, default=str), encoding="utf-8")
    return s


# ---------------- context of one call ----------------
@dataclass
class Ctx:
    agent: str
    user: str
    session: str
    language: str
    message: str
    steps: list = field(default_factory=list)
    _catalog: dict | None = None

    def note(self, step: str, t0: float | None = None, **detail):
        ms = int((time.perf_counter() - t0) * 1000) if t0 else 0
        self.steps.append({"agent": self.agent, "step": step, "ms": ms, **detail})

    async def call(self, agent: str, action: str, payload: dict | None = None, message: str = "") -> dict:
        """Call another agent (module agent or idea agent) through the bus; returns its result body."""
        from shared import agent_bus

        t0 = time.perf_counter()
        a = agent_bus.get(agent)
        if isinstance(a, IdeaAgent):
            out = await a(
                {
                    "user_id": self.user,
                    "session_id": self.session,
                    "language": self.language,
                    "message": message,
                    # action None: the agent's own LLM routes the message; the caller writes the final answer
                    "payload": {"action": action, "args": payload or {}, "reply": False},
                }
            )
            body = dict(out.get("result") or {})
            if out.get("question"):
                body["question"] = out["question"]
            ok = "error" not in body
            self.steps.append(
                {
                    "agent": self.agent,
                    "step": "agent",
                    "to": agent,
                    "action": action,
                    "ms": int((time.perf_counter() - t0) * 1000),
                    "ok": ok,
                    "sub_steps": body.get("steps", []),
                }
            )
            return body
        out = await a(
            {"action": action, "user_id": self.user, "payload": payload or {}, "sender": self.agent}
        )
        self.steps.append(
            {
                "agent": self.agent,
                "step": "tool",
                "to": agent,
                "action": action,
                "ms": int((time.perf_counter() - t0) * 1000),
                "ok": out.get("ok"),
                "error": out.get("error"),
            }
        )
        if not out.get("ok"):
            raise RuntimeError(f"{agent}.{action}: {out.get('error')}")
        return out.get("result") or {}

    async def catalog(self) -> dict:
        """The user's wardrobe (3D pieces from M9, else an M2 demo wardrobe), loaded once per call."""
        if self._catalog is None:
            from shared.wardrobe import catalog

            t0 = time.perf_counter()
            self._catalog = await catalog(self.user)
            self.note("wardrobe", t0, source=self._catalog["source"], pieces=len(self._catalog["items"]))
        return self._catalog

    @property
    def state(self) -> dict:
        return get_state(self.user, self.session)

    def remember(self, **values) -> None:
        update_state(self.user, self.session, **values)

    @property
    def profile(self) -> dict:
        return memory.profile(self.user)


@dataclass
class IdeaAction:
    description: str
    run: Callable[[Ctx, dict], Awaitable[dict]]
    params: dict[str, str] = field(default_factory=dict)  # name -> description (for the LLM and the card)


ROUTER = """You are the {name} agent of DressMe ({role}).
Choose the ONE action that answers the user's message and fill its arguments.
Actions:
{actions}
User taste (long-term memory): {profile}
Session state: {state}
Reply with JSON only: {{"action": "<one action name>", "args": {{...}}}}.
If the message is unclear, choose the most useful action with default arguments. Never invent a piece name."""


def writer_facts(data: dict) -> dict:
    """What the writer LLM sees: the recommended outfit first, one alternative, no ids / score internals
    (a small
    model mixes pieces of different outfits when it sees all of them)."""
    out = {}
    for k, v in data.items():
        if k in ("next_actions", "breakdown", "item_ids", "handled_by"):
            continue
        if k in ("outfits", "looks") and isinstance(v, list) and v and isinstance(v[0], dict):
            out["recommended_outfit"] = v[0].get("pieces")
            out["why_recommended"] = v[0].get("why")
            if len(v) > 1:
                out["alternative_outfit"] = v[1].get("pieces")
            continue
        out[k] = v
    return out


WRITER = """You are the {name} agent of DressMe ({role}), talking to the user.
Answer their last message using ONLY the FACTS (results of your tools). Name pieces exactly as in FACTS.
If FACTS has recommended_outfit, present exactly those pieces together as one outfit (alternative_outfit
is a backup).
Never invent a piece, a price, a date or a score: copy every number exactly as written in FACTS and never
compute a new one. 2 to 4 short sentences. Write in {language}."""


class IdeaAgent(BaseAgent[AgentCall, AgentResult]):
    """Base of every idea agent and BO orchestrator. Subclasses define CARD and actions()."""

    CARD: ClassVar[dict]
    input_model = AgentCall
    output_model = AgentResult
    default_action: ClassVar[str | None] = None

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if "CARD" in cls.__dict__:
            cls.name = cls.CARD["name"]
            cls.description = describe(cls.CARD)

    def actions(self) -> dict[str, IdeaAction]:
        raise NotImplementedError

    # -- card for other agents / the orchestrators: the BO8 card + actions with their parameters --
    def card(self) -> dict:
        return {
            "agent": self.name,
            **self.CARD,
            "actions": {
                k: {"description": a.description, "params": a.params} for k, a in self.actions().items()
            },
        }

    def health(self) -> dict:
        return {"agent": self.name, "status": "ok", "actions": sorted(self.actions())}

    RULES: ClassVar[tuple] = ()  # ((words...), "action"): guardrails that lock the action (small model)

    def rule_route(self, message: str) -> str | None:
        m = (message or "").lower()
        for words, action in self.RULES:
            if any(w in m for w in words):
                return action
        return None

    async def route(self, ctx: Ctx) -> tuple[str, dict]:
        """The agent's LLM reads the message and returns {action, args} (JSON mode). A guardrail rule,
        when one
        matches, locks the action; the arguments always come from the LLM."""
        acts = self.actions()
        if len(acts) == 1 and not next(iter(acts.values())).params:
            return next(iter(acts)), {}
        listing = "\n".join(
            f"- {k}: {a.description}" + (f" args: {json.dumps(a.params)}" if a.params else "")
            for k, a in acts.items()
        )
        prompt = ROUTER.format(
            name=self.name,
            role=self.CARD["role"],
            actions=listing,
            profile=json.dumps(ctx.profile, ensure_ascii=False),
            state=json.dumps(
                {k: v for k, v in ctx.state.items() if k not in ("history", "last_outfits")},
                ensure_ascii=False,
                default=str,
            )[:500],
        )
        t0 = time.perf_counter()
        hist = memory.recent(ctx.user, ctx.session)[-4:]
        msg = llm.chat(
            [{"role": "system", "content": prompt}, *hist, {"role": "user", "content": ctx.message}],
            fmt="json",
        )
        try:
            choice = json.loads(msg.get("content") or "{}")
        except ValueError:
            choice = {}
        action = choice.get("action")
        args = choice.get("args") if isinstance(choice.get("args"), dict) else {}
        rule = self.rule_route(ctx.message)
        how = "llm"
        if rule and rule in acts:
            how = "rule" if rule != action else "llm+rule"
            action = rule
        elif action not in acts:
            action, how = self.keyword_route(ctx.message) or self.default_action or next(iter(acts)), "guard"
        # a small model sometimes fills the arguments of another action: keep only the chosen action's own
        args = {k: v for k, v in args.items() if k in acts[action].params}
        ctx.note("llm_route", t0, decision=action, args=args, how=how)
        return action, args

    def _learn_taste(self, ctx: Ctx) -> None:
        """Long-term memory write: a stated taste ("I hate yellow") is extracted by the LLM (JSON) and
        saved in the
        profile, which every agent reads (dislikes are excluded from recommendations)."""
        t0 = time.perf_counter()
        msg = llm.chat(
            [
                {
                    "role": "system",
                    "content": "Extract the clothing preference stated by the user as JSON "
                    '{"kind": "likes" or "dislikes", "value": "short phrase, e.g. yellow"}. If none, '
                    '{"kind": "none", "value": ""}.',
                },
                {"role": "user", "content": ctx.message},
            ],
            fmt="json",
        )
        try:
            pref = json.loads(msg.get("content") or "{}")
        except ValueError:
            pref = {}
        if pref.get("kind") in ("likes", "dislikes") and str(pref.get("value") or "").strip():
            memory.remember(ctx.user, pref["kind"], str(pref["value"]))
            ctx.note("memory_write", t0, kind=pref["kind"], value=pref["value"])

    def keyword_route(self, message: str) -> str | None:
        """Fallback when the LLM picks no valid action and no rule matches. Override per agent."""
        return None

    async def write(self, ctx: Ctx, action: str, data: dict) -> str:
        facts = json.dumps({"action": action, **writer_facts(data)}, ensure_ascii=False, default=str)[:3000]
        t0 = time.perf_counter()
        hist = memory.recent(ctx.user, ctx.session)[-4:]
        msg = llm.chat(
            [
                {
                    "role": "system",
                    "content": WRITER.format(
                        name=self.name, role=self.CARD["role"], language=LANG_NAME.get(ctx.language)
                    ),
                },
                {"role": "system", "content": "FACTS: " + facts},
                *hist,
                {"role": "user", "content": ctx.message + f"\n\n(Answer in {LANG_NAME.get(ctx.language)}.)"},
            ]
        )
        ctx.note("llm_answer", t0)
        return msg.get("content", "")

    async def run(self, inp: AgentCall) -> AgentResult:
        p = inp.payload or {}
        ctx = Ctx(
            agent=self.name,
            user=memory._safe(inp.user_id, "anonymous"),
            session=inp.session_id,
            language=detect_language(inp.message, inp.language),
            message=inp.message or "",
        )
        ctx.note("memory", turns=len(memory.recent(ctx.user, ctx.session)), profile=ctx.profile)
        acts = self.actions()
        action, args = p.get("action"), p.get("args") or {}
        try:
            if ctx.message and p.get("reply", True) and PREF_WORDS.search(ctx.message):
                self._learn_taste(ctx)  # top-level turn only: long-term memory written once
            if not action:
                if not ctx.message:
                    return AgentResult(
                        agent=self.name,
                        question="What would you like me to do?",
                        result={"actions": sorted(acts)},
                    )
                action, args = await self.route(ctx)
            if action not in acts:
                return AgentResult(
                    agent=self.name, result={"error": f"unknown action {action!r}", "actions": sorted(acts)}
                )
            t0 = time.perf_counter()
            data = await acts[action].run(ctx, args if isinstance(args, dict) else {})
            ctx.note("workflow", t0, action=action)
            question = data.pop("question", None) if isinstance(data, dict) else None
            reply = data.pop("reply", None)
            want_reply = p.get("reply", bool(ctx.message))
            if want_reply and not reply and not question:
                reply = await self.write(ctx, action, data)
            if ctx.message and want_reply:  # top-level turn only (sub-agents do not re-log it)
                memory.append(ctx.user, ctx.session, "user", ctx.message)
                memory.append(ctx.user, ctx.session, "assistant", reply or question or "")
            return AgentResult(
                agent=self.name,
                question=question,
                result={
                    "action": action,
                    "reply": reply,
                    "data": data,
                    "steps": ctx.steps,
                    "model": llm.MODEL,
                },
                next_actions=data.get("next_actions", []) if isinstance(data, dict) else [],
            )
        except llm.LLMError as e:
            return AgentResult(agent=self.name, result={"error": str(e), "steps": ctx.steps})
        except Exception as e:  # noqa: BLE001  - an agent answers, it never crashes its caller
            return AgentResult(
                agent=self.name,
                result={"error": f"{type(e).__name__}: {e}", "action": action, "steps": ctx.steps},
            )


# ---------------- helpers shared by the idea agents ----------------
def names_of(cat: dict, ids: list[str], extra: dict | None = None) -> list[str]:
    n = {it["id"]: it["name"] for it in cat["items"]}
    if extra:
        n.update(extra)
    return [n.get(i, i) for i in ids]


def m2_items_payload(cat: dict) -> dict:
    return {"items": cat["m2_items"]} if cat.get("m2_items") else {}


def outfit_view(o: dict, cat: dict, extra_names: dict | None = None) -> dict:
    ids = o.get("items", [])
    return {
        "item_ids": ids,
        "pieces": names_of(cat, ids, extra_names),
        "score": round(float(o.get("score", 0)), 2),
        "why": o.get("explanation") or "; ".join(o.get("reasons", [])),
        "breakdown": o.get("score_breakdown"),
    }


def m2_names(res: dict) -> dict:
    return {k: v.get("name", k) for k, v in (res.get("items") or {}).items()}


Any_ = Any
