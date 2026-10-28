"""BO1 · Personalised recommendations: one agent per idea (or per group of close ideas) + the BO1
orchestrator.

Every agent is an IdeaAgent (shared/idea_agent.py): its LLM picks an action from a message, the action's
workflow calls the module agents (tools) through the agent bus, the LLM writes the answer from the facts.
"""

from __future__ import annotations

import colorsys
import datetime as dt
from collections import Counter

import numpy as np

from shared.idea_agent import Ctx, IdeaAction, IdeaAgent, m2_items_payload, m2_names, names_of, outfit_view
from shared.wardrobe import OCCASIONS, day_of, pick, resolve_pieces

MOODS = ("comfy", "bold", "classy")


def _weather(city: str, day: dt.date) -> dict:
    from modules.m02_recommendation.engine.weather import get_weather

    try:
        w, src = get_weather(city, day)
        return {
            "temp_c": w.get("temp_c"),
            "condition": w.get("condition"),
            "rain": w.get("rain"),
            "source": src,
        }
    except Exception:  # noqa: BLE001
        return {}


def _disliked_ids(ctx: Ctx, cat: dict) -> list[str]:
    """Long-term memory applied: pieces matching a dislike are never proposed."""
    import re

    words = [w.lower() for d in ctx.profile.get("dislikes", []) for w in re.findall(r"[a-zA-Z]{3,}", d)]
    words = [w for w in words if w not in ("clothes", "clothing", "the", "and", "wear", "don")]
    return [it["id"] for it in cat["items"] if any(w in it["name"].lower() for w in words)]


async def _recommend(
    ctx: Ctx,
    occasion: str,
    mood: str | None = None,
    day: dt.date | None = None,
    n: int = 3,
    exclude: list[str] | None = None,
    options: dict | None = None,
) -> tuple[list[dict], dict]:
    cat = await ctx.catalog()
    payload = {
        "context": {"occasion": occasion, "mood": mood, "date": day.isoformat() if day else None},
        "options": {
            "n": n,
            "exclude_item_ids": list(set(_disliked_ids(ctx, cat)) | set(exclude or [])),
            **(options or {}),
        },
        **m2_items_payload(cat),
    }
    res = await ctx.call("m02_recommendation", "recommend", payload)
    extra = m2_names(res)
    outs = [outfit_view(o, cat, extra) for o in res.get("outfits", [])]
    return outs, res.get("context") or {}


async def _day_occasion(ctx: Ctx, day: dt.date) -> dict:
    cal = await ctx.call("m04_scheduler", "calendar", {"start": day.isoformat(), "days": 1})
    d = (cal.get("days") or [{}])[0]
    return {
        "date": day.isoformat(),
        "occasion": d.get("occasion", "casual"),
        "reason": d.get("occasion_reason"),
        "events": [e.get("title") for e in d.get("events", [])],
    }


# =====================================================================================================
class DailyOutfitAgent(IdeaAgent):
    """Ideas: Daily outfit + Remix screen · Outfit builder screen · "Why this outfit" screen."""

    RULES = (
        (("why", "pourquoi", "explain"), "why"),
        (("another", "remix", "something else", "autre"), "remix"),
        (("with my", "avec mon", "avec ma", "avec mes", "around my", "build"), "build"),
        (("wear", "porte", "outfit", "tenue", "mettre"), "recommend"),
    )

    CARD = {
        "name": "daily_outfit",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 ideas (M2, M4, LLM)",
        "role": "Proposes the outfit of a day from the user's own clothes, remixes it, builds an outfit "
            "around "
        "chosen pieces and explains why an outfit was chosen.",
        "ideas": ["Daily outfit + Remix screen", "Outfit builder screen", "Why this outfit screen"],
        "when_to_use": [
            "What do I wear today / tomorrow?",
            "Give me another one",
            "Build an outfit with my jeans",
            "Why this outfit?",
        ],
        "when_not_to_use": ["Swap only the shoes -> swap (BO2)", "Laundry -> laundry (BO2)"],
        "skills": {
            "recommend": "M2",
            "occasion of the day": "M4 calendar",
            "why": "M2 score breakdown + LLM",
        },
        "handoff": [
            {"action": "preview", "label": "Show it on my avatar", "tool": "avatar_preview", "args": {}}
        ],
    }
    default_action = "recommend"

    def keyword_route(self, message: str) -> str | None:
        m = message.lower()
        if "why" in m or "pourquoi" in m:
            return "why"
        if any(w in m for w in ("another", "remix", "autre", "different")):
            return "remix"
        if any(w in m for w in ("with my", "avec mon", "avec ma", "build", "around")):
            return "build"
        return "recommend"

    def actions(self):
        return {
            "recommend": IdeaAction(
                "outfits for a day, occasion and mood",
                self.recommend,
                {
                    "day": "today | tomorrow | YYYY-MM-DD",
                    "occasion": "work | casual | event",
                    "mood": "comfy | bold | classy",
                },
            ),
            "remix": IdeaAction(
                "a different outfit from the last one (shares at most one piece)", self.remix
            ),
            "build": IdeaAction(
                "outfits built around pieces the user names",
                self.build,
                {"pieces": "piece names, comma separated", "occasion": "work | casual | event"},
            ),
            "why": IdeaAction(
                "explain why the last proposed outfit was chosen", self.why, {"n": "which outfit (1, 2 or 3)"}
            ),
        }

    async def recommend(self, ctx: Ctx, a: dict) -> dict:
        # the sentence's own words back up the LLM's arguments ("tomorrow", "demain", "work"...)
        day = day_of(a.get("day") or ctx.message)
        info = await _day_occasion(ctx, day)
        occ = pick(a.get("occasion") or ctx.message, OCCASIONS, info["occasion"])
        mood = pick(a.get("mood") or ctx.message, MOODS, None)
        outs, context = await _recommend(ctx, occ, mood, day)
        ctx.remember(
            last_outfits=outs,
            last_outfit=outs[0]["item_ids"] if outs else [],
            last_day=day.isoformat(),
            last_occasion=occ,
        )
        return {
            "day": info,
            "occasion": occ,
            "mood": mood,
            "weather": context.get("weather"),
            "outfits": outs,
            "next_actions": self.CARD["handoff"],
        }

    async def remix(self, ctx: Ctx, a: dict) -> dict:
        base = ctx.state.get("last_outfit") or []
        cat = await ctx.catalog()
        occ = ctx.state.get("last_occasion", "casual")
        res = await ctx.call(
            "m02_recommendation",
            "remix",
            {
                "base_item_ids": base,
                "context": {"occasion": occ},
                "options": {"n": 3},
                **m2_items_payload(cat),
            },
        )
        outs = [outfit_view(o, cat, m2_names(res)) for o in res.get("outfits", [])]
        if outs:
            ctx.remember(last_outfits=outs, last_outfit=outs[0]["item_ids"])
        return {"based_on": names_of(cat, base), "outfits": outs}

    async def build(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        pinned = resolve_pieces(a.get("pieces") or ctx.message, cat["items"])
        if not pinned:
            return {
                "question": "Which of your pieces should I build the outfit around?",
                "wardrobe": [it["name"] for it in cat["items"]][:30],
            }
        occ = pick(a.get("occasion"), OCCASIONS, ctx.state.get("last_occasion", "casual"))
        res = await ctx.call(
            "m02_recommendation",
            "complete",
            {
                "pinned_item_ids": [p["id"] for p in pinned],
                "context": {"occasion": occ},
                "options": {"n": 3},
                **m2_items_payload(cat),
            },
        )
        outs = [outfit_view(o, cat, m2_names(res)) for o in res.get("outfits", [])]
        if outs:
            ctx.remember(last_outfits=outs, last_outfit=outs[0]["item_ids"], last_occasion=occ)
        return {"around": [p["name"] for p in pinned], "occasion": occ, "outfits": outs}

    async def why(self, ctx: Ctx, a: dict) -> dict:
        outs = ctx.state.get("last_outfits") or []
        if not outs:
            return {"question": "Which outfit? Ask me for an outfit first."}
        try:
            n = max(1, min(len(outs), int(a.get("n") or 1)))
        except (TypeError, ValueError):
            n = 1
        o = outs[n - 1]
        cat = await ctx.catalog()
        sc = await ctx.call(
            "m02_recommendation",
            "score",
            {
                "outfits": [o["item_ids"]],
                "context": {"occasion": ctx.state.get("last_occasion", "casual")},
                **m2_items_payload(cat),
            },
        )
        scored = (sc.get("outfits") or [{}])[0]
        b = scored.get("score_breakdown") or o.get("breakdown") or {}
        main = sorted(
            ((k, v) for k, v in b.items() if isinstance(v, (int, float)) and k != "rotation_penalty"),
            key=lambda kv: -kv[1],
        )[:3]
        return {
            "outfit": o["pieces"],
            "score": scored.get("score", o["score"]),
            "breakdown": b,
            "strongest_reasons": [k for k, _ in main],
            "model_reasons": scored.get("reasons", o["why"]),
        }


# =====================================================================================================
class RotationAgent(IdeaAgent):
    """Idea: Rotation-aware penalty."""

    RULES = ((("report", "most", "how often", "stats"), "report"),)

    CARD = {
        "name": "rotation",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (M3, M2)",
        "role": "Keeps the wardrobe rotating: shows what was worn too often lately and proposes outfits that "
        "avoid the pieces worn in the last days.",
        "ideas": ["Rotation-aware penalty"],
        "when_to_use": ["I always wear the same thing", "Something I haven't worn this week"],
        "when_not_to_use": ["Pieces not worn for months -> forgotten"],
        "skills": {"wear stats": "M3", "outfits with rotation penalty": "M2"},
        "handoff": [],
    }
    default_action = "fresh_outfits"

    def actions(self):
        return {
            "report": IdeaAction(
                "what was worn most in the last 30 days and how well the wardrobe rotates", self.report
            ),
            "fresh_outfits": IdeaAction(
                "outfits without the pieces worn in the last N days",
                self.fresh,
                {"days": "window in days, default 7", "occasion": "work | casual | event"},
            ),
        }

    async def _stats(self, ctx: Ctx) -> tuple[dict, list[dict]]:
        cat = await ctx.catalog()
        st = await ctx.call("m03_wear_log", "stats", {"item_ids": [it["id"] for it in cat["items"]]})
        return cat, st.get("items") or []

    async def report(self, ctx: Ctx, a: dict) -> dict:
        cat, rows = await self._stats(ctx)
        worn = sorted([r for r in rows if r.get("wears_30d")], key=lambda r: -r["wears_30d"])
        used = sum(1 for r in rows if r.get("wears_30d"))
        return {
            "most_worn_30d": [
                {"piece": names_of(cat, [r["item_id"]])[0], "wears": r["wears_30d"]} for r in worn[:5]
            ],
            "pieces_worn_30d": used,
            "pieces_total": len(cat["items"]),
            "rotation_rate": round(used / max(1, len(cat["items"])), 2),
        }

    async def fresh(self, ctx: Ctx, a: dict) -> dict:
        try:
            days = max(1, min(30, int(a.get("days") or 7)))
        except (TypeError, ValueError):
            days = 7
        cat, rows = await self._stats(ctx)
        recent = [
            r["item_id"] for r in rows if r.get("days_since_worn") is not None and r["days_since_worn"] < days
        ]
        occ = pick(a.get("occasion"), OCCASIONS, "casual")
        outs, context = await _recommend(ctx, occ, exclude=recent, options={"rotation_window_days": days})
        if outs:
            ctx.remember(last_outfits=outs, last_outfit=outs[0]["item_ids"], last_occasion=occ)
        return {"window_days": days, "left_out_recently_worn": names_of(cat, recent)[:10], "outfits": outs}


# =====================================================================================================
class ForgottenAgent(IdeaAgent):
    """Idea: Rediscover forgotten pieces."""

    CARD = {
        "name": "forgotten",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (M3, M2)",
        "role": "Finds pieces not worn for a long time and builds outfits that bring them back.",
        "ideas": ["Rediscover forgotten pieces"],
        "when_to_use": ["What haven't I worn in a while?", "Use my forgotten clothes"],
        "when_not_to_use": ["Recently worn too often -> rotation"],
        "skills": {"forgotten pieces": "M3", "outfit around a piece": "M2 complete"},
        "handoff": [],
    }

    def actions(self):
        return {
            "rediscover": IdeaAction(
                "forgotten pieces + an outfit around the most forgotten one",
                self.rediscover,
                {"days": "not worn for at least N days, default 45"},
            )
        }

    async def rediscover(self, ctx: Ctx, a: dict) -> dict:
        try:
            days = max(7, int(a.get("days") or 45))
        except (TypeError, ValueError):
            days = 45
        cat = await ctx.catalog()
        ids = [it["id"] for it in cat["items"]]
        fg = await ctx.call("m03_wear_log", "forgotten", {"item_ids": ids, "days": days})
        rows = [r for r in fg.get("items", []) if r.get("status", "available") == "available"]
        wearable = [
            r
            for r in rows
            if any(
                it["id"] == r["item_id"] and it["category"] in ("top", "bottom", "dress", "outerwear")
                for it in cat["items"]
            )
        ]
        if not wearable:
            return {"forgotten": [], "message": f"nothing unworn for {days} days"}
        star = wearable[0]
        res = await ctx.call(
            "m02_recommendation",
            "complete",
            {
                "pinned_item_ids": [star["item_id"]],
                "context": {"occasion": "casual"},
                "options": {"n": 2},
                **m2_items_payload(cat),
            },
        )
        outs = [outfit_view(o, cat, m2_names(res)) for o in res.get("outfits", [])]
        if outs:
            ctx.remember(last_outfits=outs, last_outfit=outs[0]["item_ids"])
        return {
            "forgotten": [
                {
                    "piece": names_of(cat, [r["item_id"]])[0],
                    "days_since_worn": r.get("days_since_worn") or "never worn",
                }
                for r in wearable[:5]
            ],
            "bring_back": names_of(cat, [star["item_id"]])[0],
            "outfits": outs,
        }


# =====================================================================================================
class CapsuleAgent(IdeaAgent):
    """Idea: Capsule wardrobe mode."""

    RULES = ((("plan", "month", "mois", "week"), "plan"), (("capsule", "build", "make"), "build"))

    CARD = {
        "name": "capsule",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (M17, M4)",
        "role": "Builds a capsule wardrobe (the few pieces that make the most outfits) and plans the days "
            "with it.",
        "ideas": ["Capsule wardrobe mode"],
        "when_to_use": ["Make me a capsule of 10 pieces", "Plan my month with my capsule"],
        "when_not_to_use": ["One outfit -> daily_outfit"],
        "skills": {"capsule optimisation": "M17 (integer linear programming)", "plan": "M17 + M4"},
        "handoff": [],
    }
    default_action = "build"

    def actions(self):
        return {
            "build": IdeaAction(
                "choose N pieces that combine into the most outfits",
                self.build,
                {"size": "number of pieces 6-15", "season": "auto | spring | summer | autumn | winter"},
            ),
            "plan": IdeaAction("plan the next days with the last capsule", self.plan, {"days": "1-30"}),
        }

    async def build(self, ctx: Ctx, a: dict) -> dict:
        try:
            size = max(4, min(15, int(a.get("size") or 8)))
        except (TypeError, ValueError):
            size = 8
        season = pick(a.get("season"), ("spring", "summer", "autumn", "winter"), "auto")
        cat = await ctx.catalog()
        res = await ctx.call(
            "m17_capsule",
            "capsule",
            {"size": size, "season": season, "plan_days": 0, "method": "ilp", **m2_items_payload(cat)},
        )
        ids = [p["item_id"] if isinstance(p, dict) else p for p in res.get("pieces", [])]
        ctx.remember(capsule=ids)
        return {
            "size": size,
            "season": res.get("season"),
            "pieces": names_of(cat, ids),
            "outfits_possible": res.get("n_outfits") or len(res.get("outfits") or []),
            "by_occasion": res.get("by_occasion"),
        }

    async def plan(self, ctx: Ctx, a: dict) -> dict:
        ids = ctx.state.get("capsule")
        if not ids:
            return {"question": "Build a capsule first: how many pieces?"}
        try:
            days = max(1, min(30, int(a.get("days") or 7)))
        except (TypeError, ValueError):
            days = 7
        cat = await ctx.catalog()
        res = await ctx.call(
            "m17_capsule", "plan", {"item_ids": ids, "plan_days": days, **m2_items_payload(cat)}
        )
        plan = res.get("plan") or []
        return {
            "days": [
                {
                    "date": d.get("date"),
                    "occasion": d.get("occasion"),
                    "pieces": names_of(cat, (d.get("outfit") or {}).get("items") or d.get("items") or []),
                }
                for d in plan[:days]
            ]
        }


# =====================================================================================================
class SeasonalRefreshAgent(IdeaAgent):
    """Idea: Seasonal wardrobe refresh."""

    CARD = {
        "name": "seasonal_refresh",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (M4, M3, M2, weather)",
        "role": "Detects the change of season from the coming week's weather and proposes looks that "
            "bring back "
        "pieces suited to it.",
        "ideas": ["Seasonal wardrobe refresh"],
        "when_to_use": ["The weather is changing, what do I take out?", "Autumn looks"],
        "when_not_to_use": ["Today's outfit -> daily_outfit"],
        "skills": {"weather": "Open-Meteo", "forgotten": "M3", "looks": "M2"},
        "handoff": [],
    }

    def actions(self):
        return {
            "refresh": IdeaAction(
                "season of the coming week + looks with pieces to take out",
                self.refresh,
                {"city": "default Tunis"},
            )
        }

    async def refresh(self, ctx: Ctx, a: dict) -> dict:
        city = a.get("city") or "Tunis"
        today = dt.date.today()
        temps = [
            w.get("temp_c")
            for w in (_weather(city, today + dt.timedelta(days=k)) for k in range(0, 7, 2))
            if w.get("temp_c") is not None
        ]
        mean = round(sum(temps) / len(temps), 1) if temps else None
        season = (
            ("summer" if mean >= 26 else "spring/autumn" if mean >= 16 else "winter")
            if mean is not None
            else {12: "winter", 1: "winter", 2: "winter", 6: "summer", 7: "summer", 8: "summer"}.get(
                today.month, "autumn"
            )
        )
        cat = await ctx.catalog()
        fg = await ctx.call(
            "m03_wear_log", "forgotten", {"item_ids": [it["id"] for it in cat["items"]], "days": 60}
        )
        take_out = [r["item_id"] for r in fg.get("items", [])][:6]
        outs, context = await _recommend(ctx, "casual", options={"forgotten_after_days": 30})
        return {
            "city": city,
            "mean_temp_next_week": mean,
            "season": season,
            "take_out": names_of(cat, take_out),
            "looks": outs,
        }


# =====================================================================================================
class AvatarPreviewAgent(IdeaAgent):
    """Idea: 3D avatar preview of the daily outfit."""

    CARD = {
        "name": "avatar_preview",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (M2, M4, M9)",
        "role": "Puts the outfit of the day (or the last proposed outfit) on the user's 3D avatar.",
        "ideas": ["3D avatar preview of the daily outfit"],
        "when_to_use": ["Show it on me", "Show me my outfit in 3D"],
        "when_not_to_use": ["Choosing the outfit -> daily_outfit"],
        "skills": {"outfit": "state / M4 today", "3D": "M9 cloth physics"},
        "handoff": [],
    }

    def actions(self):
        return {
            "preview": IdeaAction(
                "the last proposed outfit (or today's) on the 3D avatar",
                self.preview,
                {"animate": "true for the turn animation"},
            )
        }

    async def preview(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        if not cat["source"].startswith("my 3D"):
            return {"available": False, "message": "add photos of your clothes in the 3D wardrobe first"}
        ids = ctx.state.get("last_outfit") or []
        if not ids:
            today = await ctx.call("m04_scheduler", "today", {})
            ids = (today.get("outfit") or {}).get("items", [])
        own = {it["id"] for it in cat["items"]}
        ids = [i for i in ids if i in own]
        if not ids:
            return {"available": False, "message": "no outfit from your 3D pieces yet"}
        r = await ctx.call("m09_avatar_3d", "outfit3d", {"piece_ids": ids, "animate": bool(a.get("animate"))})
        return {
            "available": True,
            "pieces": names_of(cat, ids),
            "piece_ids": ids,
            "status_3d": r.get("status"),
            "files": r.get("pieces"),
            "viewer": f"/beta1/demo?wear={','.join(ids)}",
        }


# =====================================================================================================
class GapFillingAgent(IdeaAgent):
    """Idea: Gap-filling suggestion (M6 not ready: the gap analysis is done here, shops come from M7)."""

    CARD = {
        "name": "gap_filling",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 idea (wardrobe analysis, M2, M7)",
        "role": "Finds the one missing piece that would unlock the most new outfits and where to buy it "
            "locally.",
        "ideas": ["Gap-filling suggestion"],
        "when_to_use": ["What am I missing?", "What should I buy next?"],
        "when_not_to_use": ["Should I buy THIS piece -> photo_piece (BO2)"],
        "skills": {"gap analysis": "category balance + colour", "shops": "M7 local catalogue"},
        "handoff": [{"action": "find", "label": "Find it in a shop", "tool": "local_shops", "args": {}}],
    }

    IDEAL = {"top": 0.38, "bottom": 0.25, "shoes": 0.17, "outerwear": 0.1, "dress": 0.1}

    def actions(self):
        return {
            "suggest": IdeaAction(
                "the missing piece that adds the most outfits (+ local shops)",
                self.suggest,
                {"budget_tnd": "max price in TND", "city": "default Tunis"},
            )
        }

    async def suggest(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        cnt = Counter(it["category"] for it in cat["items"])
        total = max(1, sum(cnt.values()))
        gaps = sorted(((self.IDEAL[c] - cnt.get(c, 0) / total, c) for c in self.IDEAL), reverse=True)
        slot = gaps[0][1]
        colours = Counter()
        for it in cat.get("m2_items") or []:
            for c in it.get("colors", [])[:1]:
                colours[c.get("name")] += 1
        neutral = next(
            (c for c in ("black", "white", "navy", "beige", "grey") if colours.get(c, 0) == 0), "black"
        )
        piece = {
            "top": f"{neutral} t-shirt",
            "bottom": f"{neutral} trousers",
            "shoes": f"{neutral} sneakers",
            "outerwear": f"{neutral} jacket",
            "dress": f"{neutral} dress",
        }[slot]
        tops, bottoms = cnt.get("top", 0), cnt.get("bottom", 0)
        gain = {
            "top": bottoms,
            "bottom": tops,
            "shoes": tops * max(1, bottoms) // 2 or 1,
            "outerwear": tops,
            "dress": cnt.get("shoes", 1),
        }[slot]
        query = f"{piece} {a.get('city') or 'Tunis'}" + (
            f" {a['budget_tnd']} TND" if a.get("budget_tnd") else ""
        )
        shops = await ctx.call("local_shops", "find", {"query": query})
        return {
            "wardrobe_by_category": dict(cnt),
            "missing_slot": slot,
            "suggested_piece": piece,
            "new_outfits_estimate": gain,
            "shops": (shops.get("data") or {}).get("results", [])[:3],
            "next_actions": self.CARD["handoff"],
        }


# =====================================================================================================
class TravelAgent(IdeaAgent):
    """Ideas: Travel outfit planner (BO1) + Packing outfits for a trip (BO2). M11 not ready: done here."""

    CARD = {
        "name": "travel",
        "version": "1.0.0",
        "owner": "BO1/BO2",
        "module": "BO1+BO2 idea (weather, M2)",
        "role": "Plans an outfit per day of a trip from the destination's weather and packs the fewest "
            "pieces.",
        "ideas": ["Travel outfit planner", "Packing outfits for a trip"],
        "when_to_use": ["I'm going to Paris for 4 days", "What do I pack for Sousse this weekend?"],
        "when_not_to_use": ["One day at home -> daily_outfit"],
        "skills": {"weather per day": "Open-Meteo", "outfits": "M2", "fewest pieces": "greedy reuse"},
        "handoff": [],
    }

    def actions(self):
        return {
            "plan": IdeaAction(
                "outfit per day + packing list with the fewest pieces",
                self.plan,
                {
                    "city": "destination",
                    "days": "number of days 1-10",
                    "start": "YYYY-MM-DD, default tomorrow",
                    "occasion": "casual | work | event",
                },
            )
        }

    async def plan(self, ctx: Ctx, a: dict) -> dict:
        city = (a.get("city") or "").strip() or None
        if not city:
            return {"question": "Where are you going, and for how many days?"}
        try:
            days = max(1, min(10, int(a.get("days") or 3)))
        except (TypeError, ValueError):
            days = 3
        start = day_of(a.get("start") or "tomorrow")
        occ = pick(a.get("occasion"), OCCASIONS, "casual")
        cat = await ctx.catalog()
        packed: set[str] = set()
        plan = []
        prev: list[str] = []
        for k in range(days):
            d = start + dt.timedelta(days=k)
            w = _weather(city, d)
            res = await ctx.call(
                "m02_recommendation",
                "recommend",
                {
                    "context": {
                        "occasion": occ,
                        "city": city,
                        "date": d.isoformat(),
                        "weather": {
                            k2: w[k2] for k2 in ("temp_c", "condition", "rain") if w.get(k2) is not None
                        }
                        or None,
                    },
                    "options": {
                        "n": 6,
                        "exclude_item_ids": _disliked_ids(ctx, cat),
                        "rotation_window_days": 0,
                    },
                    **m2_items_payload(cat),
                },
            )
            cands = [o["items"] for o in res.get("outfits", [])] or [[]]
            best = max(cands, key=lambda ids: len(set(ids) & packed) - 3 * (sorted(ids) == sorted(prev)))
            packed |= set(best)
            prev = best
            plan.append({"date": d.isoformat(), "weather": w, "pieces": names_of(cat, best, m2_names(res))})
        return {
            "city": city,
            "days": plan,
            "packing_list": names_of(cat, sorted(packed)),
            "pieces_to_pack": len(packed),
        }


# =====================================================================================================
class StyleInsightsAgent(IdeaAgent):
    """Ideas: Personal colour palette · Style drift detection · Favourite looks / lookbook."""

    RULES = (
        (("drift", "chang", "évolu", "evolv"), "drift"),
        (("favourite", "favorite", "lookbook", "préfér"), "lookbook"),
        (("colour", "color", "palette", "couleur"), "palette"),
    )

    CARD = {
        "name": "style_insights",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 ideas (M3, wardrobe colours)",
        "role": "Reads the wardrobe and the wear history: the user's colour palette, how their style is "
            "drifting, "
        "and their favourite looks.",
        "ideas": ["Personal colour palette", "Style drift detection", "Favourite looks / lookbook"],
        "when_to_use": ["What are my colours?", "Is my style changing?", "My favourite outfits"],
        "when_not_to_use": ["What do I wear today -> daily_outfit"],
        "skills": {
            "palette": "wardrobe colours x wear counts + colour harmony",
            "drift": "M3 history",
            "lookbook": "M3 repeated / posted looks",
        },
        "handoff": [],
    }

    def keyword_route(self, message: str) -> str | None:
        m = message.lower()
        if "drift" in m or "chang" in m or "évolu" in m:
            return "drift"
        if "favourite" in m or "favorite" in m or "lookbook" in m or "préféré" in m:
            return "lookbook"
        return "palette"

    def actions(self):
        return {
            "palette": IdeaAction(
                "the user's colour palette weighted by what they wear + matching colours", self.palette
            ),
            "drift": IdeaAction(
                "how the colours / types worn in the last 30 days differ from before", self.drift
            ),
            "lookbook": IdeaAction("favourite looks: outfits worn most often or posted", self.lookbook),
        }

    async def _colours(self, ctx: Ctx) -> dict[str, dict]:
        cat = await ctx.catalog()
        out = {}
        for it in cat.get("m2_items") or []:
            c = (it.get("colors") or [{}])[0]
            out[it["item_id"]] = {
                "name": c.get("name", "?"),
                "hex": c.get("hex", "#808080"),
                "category": it.get("category"),
            }
        return out

    async def palette(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        col = await self._colours(ctx)
        st = await ctx.call("m03_wear_log", "stats", {"item_ids": list(col)})
        wears = {r["item_id"]: r.get("wear_count", 0) for r in st.get("items", [])}
        weight = Counter()
        hexes = {}
        for i, c in col.items():
            weight[c["name"]] += 1 + wears.get(i, 0)
            hexes[c["name"]] = c["hex"]
        top = [n for n, _ in weight.most_common(5)]

        def harmony(hx: str) -> str:
            r, g, b = (int(hx.lstrip("#")[k : k + 2], 16) / 255 for k in (0, 2, 4))
            h, l_, s = colorsys.rgb_to_hls(r, g, b)
            r2, g2, b2 = colorsys.hls_to_rgb((h + 0.5) % 1, l_, s)
            return f"#{int(r2 * 255):02x}{int(g2 * 255):02x}{int(b2 * 255):02x}"

        total = sum(weight.values()) or 1
        return {
            "palette": [{"colour": n, "hex": hexes[n], "share": round(weight[n] / total, 2)} for n in top],
            "accent_suggestions": [{"with": n, "complementary_hex": harmony(hexes[n])} for n in top[:3]],
            "pieces": len(cat["items"]),
        }

    async def _history(self, ctx: Ctx, since: dt.date) -> list[dict]:
        h = await ctx.call("m03_wear_log", "history", {"since": since.isoformat(), "limit": 2000})
        return h.get("entries") or h.get("items") or []

    async def drift(self, ctx: Ctx, a: dict) -> dict:
        col = await self._colours(ctx)
        today = dt.date.today()
        hist = await self._history(ctx, today - dt.timedelta(days=120))
        recent, before = Counter(), Counter()
        for e in hist:
            d = dt.date.fromisoformat(str(e["date"])[:10])
            bucket = recent if (today - d).days <= 30 else before
            for i in e.get("item_ids", []):
                if i in col:
                    bucket[col[i]["name"]] += 1
        rt, bt = sum(recent.values()) or 1, sum(before.values()) or 1
        changes = sorted(
            ((recent[c] / rt - before[c] / bt, c) for c in set(recent) | set(before)), reverse=True
        )
        return {
            "worn_last_30d": sum(recent.values()),
            "worn_31_120d": sum(before.values()),
            "rising": [{"colour": c, "change": round(v, 2)} for v, c in changes[:3] if v > 0.02],
            "fading": [{"colour": c, "change": round(v, 2)} for v, c in changes[::-1][:3] if v < -0.02],
        }

    async def lookbook(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        hist = await self._history(ctx, dt.date.today() - dt.timedelta(days=365))
        looks = Counter()
        posted = set()
        for e in hist:
            key = tuple(sorted(e.get("item_ids", [])))
            if len(key) >= 2:
                looks[key] += 1
                if e.get("posted"):
                    posted.add(key)
        fav = [k for k, _ in looks.most_common(5)]
        return {
            "favourite_looks": [
                {"pieces": names_of(cat, list(k)), "times_worn": looks[k], "posted": k in posted} for k in fav
            ]
        }


# =====================================================================================================
class BOOrchestrator(IdeaAgent):
    """A BO agent. Two-stage routing:
      1. its LLM reads the cards of the idea agents (its own + the partner BO's) and picks ONE agent
         (strong keywords first: guardrails for a small model)
      2. the message goes to that idea agent, whose own LLM picks the action and its arguments
    A partner-BO idea is asked to the partner orchestrator, which hands it to its idea agent.
    Programmatic callers can skip both LLMs with payload {"action": "<agent>.<action>", "args": {...}}."""

    IDEAS: tuple = ()
    PARTNER: str = ""
    PARTNER_IDEAS: tuple = ()
    RULES: tuple = ()  # ((words...), "agent" or "partner:agent")

    def _cards(self) -> dict:
        from shared import agent_bus

        out = {}
        for name in self.IDEAS:
            out[name] = agent_bus.get(name)
        for name in self.PARTNER_IDEAS:
            try:
                out[f"{self.PARTNER}:{name}"] = agent_bus.get(name)
            except KeyError:
                pass
        return out

    def actions(self):
        acts = {}
        for key, agent in self._cards().items():
            target, _, idea = key.partition(":") if ":" in key else ("", "", key)
            card = agent.CARD
            desc = f"{card['role']} Ideas: {', '.join(card.get('ideas') or [])}." + (
                f" (via the {self.PARTNER} agent)" if target else ""
            )
            acts[key] = IdeaAction(desc, self._partner_message(idea) if target else self._message(idea))
            for act, spec in agent.actions().items():  # structured entries, not shown to the LLM
                acts[f"{key}.{act}"] = IdeaAction(
                    f"[{key}] {spec.description}",
                    self._partner(f"{idea}.{act}") if target else self._delegate(idea, act),
                    spec.params,
                )
        return acts

    def keyword_route(self, message: str) -> str | None:
        m = message.lower()
        for words, target in self.RULES:
            if any(w in m for w in words):
                return target
        return None

    async def route(self, ctx: Ctx) -> tuple[str, dict]:
        import json
        import time

        from shared import local_llm as llm

        rule = self.keyword_route(ctx.message)
        if rule:
            ctx.note("rule_route", decision=rule, why="guardrail keyword")
            return rule, {}
        cards = self._cards()
        listing = "\n".join(
            f"- {k}: {a.CARD['role']} Examples: {'; '.join(a.CARD.get('when_to_use') or [])}"
            for k, a in cards.items()
        )
        prompt = (
            f"You are the {self.name} agent of DressMe ({self.CARD['role']})\n"
            f"Choose the ONE agent that should handle the user's message.\nAgents:\n{listing}\n"
            'Reply with JSON only: {"agent": "<agent name exactly as listed>"}'
        )
        t0 = time.perf_counter()
        hist = __import__("shared.agent_memory", fromlist=["recent"]).recent(ctx.user, ctx.session)[-4:]
        msg = llm.chat(
            [{"role": "system", "content": prompt}, *hist, {"role": "user", "content": ctx.message}],
            fmt="json",
        )
        try:
            choice = (json.loads(msg.get("content") or "{}") or {}).get("agent")
        except ValueError:
            choice = None
        if choice not in cards:  # tolerate "forgotten" for "personalised_recommendations:forgotten"
            choice = next((k for k in cards if k.split(":")[-1] == str(choice).split(":")[-1]), None)
        guard = choice is None
        choice = choice or self.default_action
        ctx.note("llm_route", t0, decision=choice, **({"guard": True} if guard else {}))
        return choice, {}

    def _message(self, agent: str):
        async def run(ctx: Ctx, args: dict) -> dict:
            body = await ctx.call(agent, None, args, message=ctx.message)
            if "error" in body:
                return {"handled_by": agent, "error": body["error"]}
            out = {"handled_by": f"{agent}.{body.get('action')}", **(body.get("data") or {})}
            if body.get("question"):
                out["question"] = body["question"]
            return out

        return run

    def _partner_message(self, agent: str):
        async def run(ctx: Ctx, args: dict) -> dict:
            body = await ctx.call(self.PARTNER, agent, args, message=ctx.message)
            data = body.get("data") or {}
            return {**data, "handled_by": f"{self.PARTNER} -> {data.get('handled_by', agent)}"}

        return run

    def _delegate(self, agent: str, action: str):
        async def run(ctx: Ctx, args: dict) -> dict:
            body = await ctx.call(agent, action, args)
            if "error" in body:
                return {"handled_by": agent, "error": body["error"]}
            return {"handled_by": f"{agent}.{action}", **(body.get("data") or {})}

        return run

    def _partner(self, target: str):
        async def run(ctx: Ctx, args: dict) -> dict:
            body = await ctx.call(self.PARTNER, target, args)
            return {"handled_by": f"{self.PARTNER} -> {target}", **(body.get("data") or {})}

        return run


class BO1Orchestrator(BOOrchestrator):
    """BO1 agent: Personalised recommendations."""

    CARD = {
        "name": "personalised_recommendations",
        "version": "1.0.0",
        "owner": "BO1",
        "module": "BO1 orchestrator",
        "role": "Personalised recommendations agent: understands the request and hands it to the right "
            "BO1 idea "
        "agent (outfit of the day, remix, builder, why, rotation, forgotten pieces, capsule, seasonal "
        "refresh, 3D preview, gap filling, travel, palette / drift / lookbook).",
        "ideas": ["all BO1 ideas"],
        "when_to_use": ["choosing / understanding outfits"],
        "when_not_to_use": ["time savers (laundry, swap, widget) -> time_optimisation"],
        "skills": {},
        "handoff": [],
    }
    default_action = "daily_outfit"
    IDEAS = (
        "daily_outfit",
        "rotation",
        "forgotten",
        "capsule",
        "seasonal_refresh",
        "avatar_preview",
        "gap_filling",
        "travel",
        "style_insights",
    )
    PARTNER = "time_optimisation"
    PARTNER_IDEAS = (
        "daily_plan",
        "swap",
        "laundry",
        "event_looks",
        "local_shops",
        "photo_piece",
        "declutter",
    )
    RULES = (
        (("laundry", "lessive", "dirty", " sale", "washed"), "time_optimisation:laundry"),
        (("change the shoes", "swap", "other shoes", "autres chaussures"), "time_optimisation:swap"),
        (("haven't worn", "forgot", "oubli", "long time"), "forgotten"),
        (("pack", "trip", "travel", "voyage", "valise", "je pars"), "travel"),
        (("capsule",), "capsule"),
        (("3d", "avatar", "show it on me"), "avatar_preview"),
        (("palette", "my colours", "my colors", "drift", "lookbook", "favourite looks"), "style_insights"),
        (("same thing", "rotation", "this week"), "rotation"),
        (("missing", "buy next", "manque"), "gap_filling"),
        (("season", "saison"), "seasonal_refresh"),
        (("tnd", "shop", "boutique", "magasin"), "time_optimisation:local_shops"),
    )


AGENTS = [
    DailyOutfitAgent(),
    RotationAgent(),
    ForgottenAgent(),
    CapsuleAgent(),
    SeasonalRefreshAgent(),
    AvatarPreviewAgent(),
    GapFillingAgent(),
    TravelAgent(),
    StyleInsightsAgent(),
    BO1Orchestrator(),
]

_np = np
