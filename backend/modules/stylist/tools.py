"""What the Stylist can do. Each tool is a small, typed wrapper over the module agents (M2, M3, M4, M9, M17),
reached through the agent bus exactly like any other BO's agent would. Arguments coming from the LLM are
validated and clamped here (a 3B model sometimes fills them badly)."""

from __future__ import annotations

import datetime as dt
import re

from shared.agent_bus import ask

from . import memory

ME = "stylist"
from shared.wardrobe import (  # noqa: E402,F401  (moved to shared: used by every agent)
    MOODS,
    OCCASIONS,
    catalog,
    resolve_pieces,
    retrieve,
)
from shared.wardrobe import day_of as _day  # noqa: E402
from shared.wardrobe import pick as _pick  # noqa: E402

TOOL_SPECS = [
    (
        "day_context",
        "Occasion of a day (from the user's calendar: work / casual / event, events, holidays) and its "
        "weather forecast. Call it first when the user talks about a day.",
        {"day": {"type": "string", "description": "today, tomorrow or YYYY-MM-DD"}},
        [],
    ),
    ("unavailable_pieces", "Pieces that cannot be worn now (in the laundry or lent).", {}, []),
    (
        "recommend_outfits",
        "Outfits from the user's wardrobe for an occasion and mood (pieces in the laundry are "
        "already excluded).",
        {
            "occasion": {"type": "string", "enum": list(OCCASIONS)},
            "mood": {"type": "string", "enum": ["any", *MOODS]},
            "day": {"type": "string", "description": "today, tomorrow or YYYY-MM-DD"},
        },
        ["occasion"],
    ),
    (
        "complete_outfit",
        "Build outfits around pieces the user wants to wear.",
        {
            "pieces": {"type": "string", "description": "names of the pieces, comma separated"},
            "occasion": {"type": "string", "enum": list(OCCASIONS)},
        },
        ["pieces"],
    ),
    (
        "set_laundry",
        "Put pieces in the laundry, or back in the closet.",
        {
            "pieces": {"type": "string", "description": "names of the pieces, comma separated"},
            "status": {"type": "string", "enum": ["laundry", "available"]},
        },
        ["pieces", "status"],
    ),
    (
        "log_worn",
        "Record that the user wore pieces today.",
        {"pieces": {"type": "string", "description": "names of the pieces, comma separated"}},
        ["pieces"],
    ),
    ("forgotten_pieces", "Pieces not worn for a long time.", {}, []),
    (
        "build_capsule",
        "A capsule wardrobe: the few pieces that make the most outfits.",
        {"size": {"type": "integer", "description": "number of pieces, 6 to 15"}},
        [],
    ),
    (
        "show_on_avatar",
        "Put an outfit on the user's 3D avatar.",
        {"pieces": {"type": "string", "description": "names of the pieces, comma separated"}},
        ["pieces"],
    ),
    (
        "remember_preference",
        "Save something about the user's taste to remember in future conversations.",
        {
            "kind": {"type": "string", "enum": ["likes", "dislikes", "notes"]},
            "value": {"type": "string", "description": "e.g. 'yellow', 'oversize fits', 'works in a bank'"},
        },
        ["kind", "value"],
    ),
]


def ollama_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": d,
                "parameters": {"type": "object", "properties": p, "required": r},
            },
        }
        for n, d, p, r in TOOL_SPECS
    ]


def _outfit_view(o: dict, names: dict) -> dict:
    return {
        "items": [{"id": i, "name": names.get(i, i)} for i in o.get("items", [])],
        "score": round(float(o.get("score", 0)), 2),
        "why": o.get("explanation") or "; ".join(o.get("reasons", [])),
    }


class Toolbox:
    """Tools bound to one user and one request; collects the structured results for the caller."""

    def __init__(self, user: str, cat: dict):
        self.user, self.cat = user, cat
        self.names = {it["id"]: it["name"] for it in cat["items"]}
        self.outfits: list[dict] = []
        self.avatar: dict | None = None
        self.context: dict = {}

    async def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, "t_" + name, None)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        return await fn(args if isinstance(args, dict) else {})

    def disliked_ids(self) -> list[str]:
        """Long-term memory applied: pieces matching something the user dislikes are never proposed."""
        bad = [
            w.lower() for w in memory.profile(self.user)["dislikes"] for w in re.findall(r"[a-zA-Z]{3,}", w)
        ]
        bad = [w for w in bad if w not in ("clothes", "clothing", "the", "and", "wear")]
        return [i for i, n in self.names.items() if any(w in n.lower() for w in bad)]

    def _m2_payload(self, occasion: str, mood: str | None, day: dt.date | None) -> dict:
        p = {
            "context": {"occasion": occasion, "mood": mood, "date": day.isoformat() if day else None},
            "options": {"n": 3, "exclude_item_ids": self.disliked_ids()},
        }
        if self.cat["m2_items"]:
            p["items"] = self.cat["m2_items"]
        from shared.style_taste import taste_vector

        if taste := taste_vector(self.user):  # M5 (BO4): the taste learnt from the user's swipes
            p["options"]["style_vector"] = taste
        return p

    async def t_day_context(self, a: dict) -> dict:
        day = _day(a.get("day"))
        cal = await ask("m04_scheduler", "calendar", {"start": day.isoformat(), "days": 1}, self.user, ME)
        d = ((cal.get("result") or {}).get("days") or [{}])[0]
        from modules.m02_recommendation.engine.weather import get_weather

        try:
            w, _src = get_weather("Tunis", day)
        except Exception:  # noqa: BLE001
            w = {}
        self.context = {
            "date": day.isoformat(),
            "occasion": d.get("occasion", "casual"),
            "reason": d.get("occasion_reason"),
            "events": [e.get("title") for e in d.get("events", [])],
            "holidays": [h.get("name") for h in d.get("holidays", [])],
            "weather": {k: w.get(k) for k in ("temp_c", "condition", "rain") if k in w},
        }
        return self.context

    async def t_unavailable_pieces(self, a: dict) -> dict:
        r = await ask("m03_wear_log", "states", {"item_ids": list(self.names)}, self.user, ME)
        res = r.get("result") or {}
        st = {x["item_id"]: x["status"] for x in res.get("items", []) if x.get("status") != "available"}
        return {"unavailable": [{"name": self.names.get(i, i), "status": s} for i, s in st.items()]}

    async def t_recommend_outfits(self, a: dict) -> dict:
        occ = _pick(a.get("occasion"), OCCASIONS, self.context.get("occasion", "casual"))
        mood = _pick(a.get("mood"), MOODS, None)
        day = (
            _day(a.get("day"))
            if a.get("day")
            else (dt.date.fromisoformat(self.context["date"]) if self.context.get("date") else None)
        )
        r = await ask("m02_recommendation", "recommend", self._m2_payload(occ, mood, day), self.user, ME)
        if not r.get("ok"):
            return {"error": r.get("error")}
        res = r["result"]
        for k, v in (res.get("items") or {}).items():
            self.names.setdefault(k, v.get("name", k))
        self.outfits = [_outfit_view(o, self.names) for o in res.get("outfits", [])]
        w = (res.get("context") or {}).get("weather") or {}
        return {
            "occasion": occ,
            "mood": mood,
            "weather": w,
            "outfits": [
                {"n": i + 1, "pieces": [p["name"] for p in o["items"]], "score": o["score"], "why": o["why"]}
                for i, o in enumerate(self.outfits)
            ],
        }

    async def t_complete_outfit(self, a: dict) -> dict:
        pinned = resolve_pieces(a.get("pieces"), self.cat["items"])
        if not pinned:
            return {
                "error": "piece not found in the wardrobe",
                "wardrobe": [it["name"] for it in self.cat["items"]],
            }
        occ = _pick(a.get("occasion"), OCCASIONS, self.context.get("occasion", "casual"))
        p = self._m2_payload(occ, None, None)
        p["pinned_item_ids"] = [x["id"] for x in pinned]
        r = await ask("m02_recommendation", "complete", p, self.user, ME)
        if not r.get("ok"):
            return {"error": r.get("error")}
        for k, v in (r["result"].get("items") or {}).items():
            self.names.setdefault(k, v.get("name", k))
        self.outfits = [_outfit_view(o, self.names) for o in r["result"].get("outfits", [])]
        return {
            "around": [x["name"] for x in pinned],
            "outfits": [
                {"n": i + 1, "pieces": [p["name"] for p in o["items"]], "score": o["score"]}
                for i, o in enumerate(self.outfits)
            ],
        }

    async def t_set_laundry(self, a: dict) -> dict:
        pcs = resolve_pieces(a.get("pieces"), self.cat["items"])
        status = "available" if "avail" in str(a.get("status", "")).lower() else "laundry"
        if not pcs:
            return {"error": "piece not found in the wardrobe"}
        r = await ask(
            "m03_wear_log", "status", {"item_ids": [p["id"] for p in pcs], "status": status}, self.user, ME
        )
        return {"done": r.get("ok"), "status": status, "pieces": [p["name"] for p in pcs]}

    async def t_log_worn(self, a: dict) -> dict:
        pcs = resolve_pieces(a.get("pieces"), self.cat["items"])
        if not pcs:
            return {"error": "piece not found in the wardrobe"}
        r = await ask(
            "m03_wear_log", "worn", {"item_ids": [p["id"] for p in pcs], "source": "chat"}, self.user, ME
        )
        return {"done": r.get("ok"), "pieces": [p["name"] for p in pcs]}

    async def t_forgotten_pieces(self, a: dict) -> dict:
        r = await ask("m03_wear_log", "forgotten", {"item_ids": list(self.names), "days": 30}, self.user, ME)
        res = r.get("result") or {}
        rows = res.get("items") or res.get("pieces") or []
        return {
            "forgotten": [
                {"name": self.names.get(x.get("item_id"), x.get("item_id")), "days": x.get("days_since_worn")}
                for x in rows[:8]
            ]
        }

    async def t_build_capsule(self, a: dict) -> dict:
        try:
            size = int(a.get("size") or 10)
        except (TypeError, ValueError):
            size = 10
        p = {"size": max(4, min(15, size)), "plan_days": 0, "method": "ilp"}
        if self.cat["m2_items"]:
            p["items"] = self.cat["m2_items"]
        r = await ask("m17_capsule", "capsule", p, self.user, ME)
        if not r.get("ok"):
            return {"error": r.get("error")}
        res = r["result"]
        pieces = res.get("pieces") or []
        ids = [x["item_id"] if isinstance(x, dict) else x for x in pieces]
        return {"pieces": [self.names.get(i, i) for i in ids], "outfits": len(res.get("outfits") or [])}

    async def t_show_on_avatar(self, a: dict) -> dict:
        pcs = resolve_pieces(a.get("pieces"), self.cat["items"])
        if not pcs and self.outfits:
            pcs = [{"id": i["id"], "name": i["name"]} for i in self.outfits[0]["items"]]
        if not pcs:
            return {"error": "which pieces?"}
        r = await ask("m09_avatar_3d", "outfit3d", {"piece_ids": [p["id"] for p in pcs]}, self.user, ME)
        self.avatar = {"piece_ids": [p["id"] for p in pcs], "status": (r.get("result") or {}).get("status")}
        return {"on_avatar": [p["name"] for p in pcs], "status": self.avatar["status"]}

    async def t_remember_preference(self, a: dict) -> dict:
        p = memory.remember(self.user, str(a.get("kind", "notes")), str(a.get("value", "")))
        return {"saved": True, "profile": p}
