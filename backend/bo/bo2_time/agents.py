"""BO2 · Time optimisation: one agent per idea (or group of close ideas) + the BO2 orchestrator.

"Quick natural-language request" (BO2) is the BO2 orchestrator itself: one sentence -> the right agent.
"Packing outfits for a trip" is served by the shared `travel` agent (BO1 file).
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import numpy as np

from bo.bo1_recommendations.agents import BOOrchestrator
from shared.idea_agent import Ctx, IdeaAction, IdeaAgent, m2_items_payload, m2_names, names_of, outfit_view
from shared.wardrobe import OCCASIONS, day_of, pick, resolve_pieces

SLOTS = ("top", "bottom", "dress", "outerwear", "shoes")


def _day_view(res: dict, cat: dict) -> dict:
    o = res.get("outfit") or {}
    return {
        "date": res.get("date"),
        "occasion": res.get("occasion"),
        "weather": res.get("weather"),
        "approved": res.get("approved"),
        "pieces": names_of(cat, o.get("items", [])),
        "item_ids": o.get("items", []),
        "option": f"{(res.get('choice') or 0) + 1}/{res.get('options') or 1}",
        "summary": res.get("summary"),
        "cached": res.get("source") != "on_demand",
    }


# =====================================================================================================
class DailyPlanAgent(IdeaAgent):
    """Ideas: Outfit of the day in one screen (cached) · Tomorrow's outfit the night before ·
    Notification with the outfit ready · Home-screen widget."""

    CARD = {
        "name": "daily_plan",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 ideas (M4, M2, M3)",
        "role": "Gives the outfit of today or tomorrow already prepared (cached by the scheduler), "
            "approves or "
        "changes it, marks it worn, and serves the notification and the home-screen widget.",
        "ideas": [
            "Outfit of the day in one screen (cached)",
            "Tomorrow's outfit the night before",
            "Notification with the outfit ready",
            "Home-screen widget",
        ],
        "when_to_use": ["Today's outfit", "Tomorrow's outfit", "OK I take it", "Change it", "I wore it"],
        "when_not_to_use": ["Explain / build an outfit -> daily_outfit (BO1)"],
        "skills": {"cached outfit, approve, change, wear": "M4", "notifications, widget": "M4"},
        "handoff": [],
    }
    default_action = "today"
    RULES = (
        (("tomorrow", "demain"), "tomorrow"),
        (("i take it", "approve", "je prends", "lock"), "approve"),
        (("another option", "change it", "next option"), "change"),
        (("i wore", "i'm wearing", "j'ai porté"), "wear"),
        (("notif",), "notifications"),
        (("widget",), "widget"),
        (("week", "semaine"), "week"),
        (("today", "aujourd'hui"), "today"),
    )

    def keyword_route(self, message: str) -> str | None:
        m = message.lower()
        for words, act in (
            (("tomorrow", "demain"), "tomorrow"),
            (("approve", "i take", "ok ", "je prends"), "approve"),
            (("change", "another", "autre"), "change"),
            (("wore", "worn", "porté"), "wear"),
            (("notif",), "notifications"),
            (("widget",), "widget"),
            (("week", "semaine"), "week"),
        ):
            if any(w in m for w in words):
                return act
        return "today"

    def actions(self):
        day = {"day": "today | tomorrow | YYYY-MM-DD"}
        return {
            "today": IdeaAction("the prepared outfit of today (one screen)", self.today),
            "tomorrow": IdeaAction(
                "tomorrow's outfit, prepared the night before with tomorrow's forecast", self.tomorrow
            ),
            "approve": IdeaAction("lock the proposed outfit of a day", self.approve, day),
            "change": IdeaAction("next option for a day", self.change, day),
            "wear": IdeaAction("wear the outfit of today (logged in the wear log)", self.wear),
            "week": IdeaAction("the next 7 days planned, no piece repeated", self.week),
            "notifications": IdeaAction("notifications with the outfit ready", self.notifications),
            "widget": IdeaAction("compact payload of the home-screen widget", self.widget),
        }

    async def _day(self, ctx: Ctx, action: str, day: dt.date | None = None) -> dict:
        cat = await ctx.catalog()
        payload = {"date": day.isoformat()} if day else {}
        res = await ctx.call("m04_scheduler", action, payload)
        view = _day_view(res, cat)
        ctx.remember(last_outfit=view["item_ids"], last_day=view["date"], last_occasion=view["occasion"])
        return view

    async def today(self, ctx: Ctx, a: dict) -> dict:
        return await self._day(ctx, "today")

    async def tomorrow(self, ctx: Ctx, a: dict) -> dict:
        return await self._day(ctx, "tomorrow")

    async def approve(self, ctx: Ctx, a: dict) -> dict:
        return {
            "approved": True,
            **(await self._day(ctx, "approve", day_of(a.get("day") or ctx.state.get("last_day")))),
        }

    async def change(self, ctx: Ctx, a: dict) -> dict:
        return await self._day(ctx, "change", day_of(a.get("day") or ctx.state.get("last_day")))

    async def wear(self, ctx: Ctx, a: dict) -> dict:
        return {"logged_as_worn": True, **(await self._day(ctx, "wear"))}

    async def week(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        res = await ctx.call("m04_scheduler", "week", {"days": 7})
        return {
            "days": [
                {
                    "date": d.get("date"),
                    "occasion": d.get("occasion"),
                    "pieces": names_of(cat, (d.get("outfit") or {}).get("items", [])),
                }
                for d in res.get("days", [])
            ]
        }

    async def notifications(self, ctx: Ctx, a: dict) -> dict:
        await ctx.call("m04_scheduler", "run", {"job": "due"})
        res = await ctx.call("m04_scheduler", "notifications", {"limit": 5})
        return {
            "unread": res.get("unread"),
            "notifications": [
                {"title": n.get("title"), "body": n.get("body"), "actions": n.get("actions")}
                for n in res.get("notifications", [])[:5]
            ],
        }

    async def widget(self, ctx: Ctx, a: dict) -> dict:
        res = await ctx.call("m04_scheduler", "widget", {})
        return {
            k: res.get(k)
            for k in ("date", "temp_c", "condition", "occasion", "summary", "approved", "deep_link")
        }


# =====================================================================================================
class SwapAgent(IdeaAgent):
    """Idea: One-tap swap of a single piece."""

    CARD = {
        "name": "swap",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 idea (M2)",
        "role": "Replaces one piece of the current outfit (shoes, top, bottom...) and keeps the rest.",
        "ideas": ["One-tap swap of a single piece"],
        "when_to_use": ["Change the shoes", "Another top with this"],
        "when_not_to_use": ["A whole new outfit"],
        "skills": {"swap": "M2"},
        "handoff": [],
    }

    def actions(self):
        return {
            "swap": IdeaAction(
                "replace one slot of the current outfit",
                self.swap,
                {"slot": "top | bottom | dress | outerwear | shoes"},
            )
        }

    async def swap(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        ids = ctx.state.get("last_outfit") or []
        if not ids:
            res = await ctx.call("m04_scheduler", "today", {})
            ids = (res.get("outfit") or {}).get("items", [])
        slot = pick(
            a.get("slot") or ctx.message, SLOTS + ("shirt", "pants", "jean", "sneaker", "chaussure"), "shoes"
        )
        slot = {
            "shirt": "top",
            "pants": "bottom",
            "jean": "bottom",
            "sneaker": "shoes",
            "chaussure": "shoes",
        }.get(slot, slot)
        cats = {it["id"]: it["category"] for it in cat["items"]}
        if slot not in {cats.get(i) for i in ids}:
            slot = next((cats.get(i) for i in ids if cats.get(i)), "shoes")
        res = await ctx.call(
            "m02_recommendation",
            "swap",
            {
                "item_ids": ids,
                "slot": slot,
                "context": {"occasion": ctx.state.get("last_occasion", "casual")},
                "options": {"n": 3},
                **m2_items_payload(cat),
            },
        )
        outs = [outfit_view(o, cat, m2_names(res)) for o in res.get("outfits", [])]
        if outs:
            ctx.remember(last_outfit=outs[0]["item_ids"], last_outfits=outs)
        return {
            "slot": slot,
            "before": names_of(cat, ids),
            "after": outs[0]["pieces"] if outs else [],
            "alternatives": [o["pieces"] for o in outs[1:]],
        }


# =====================================================================================================
class LaundryAgent(IdeaAgent):
    """Idea: Laundry / unavailable UI."""

    CARD = {
        "name": "laundry",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 idea (M3)",
        "role": "Keeps track of what is in the laundry or lent so it is never suggested, and brings it back.",
        "ideas": ["Laundry / unavailable UI"],
        "when_to_use": [
            "My jeans are dirty",
            "Laundry is done",
            "What's in the laundry?",
            "I lent my jacket",
        ],
        "when_not_to_use": ["What to wear -> daily_plan / daily_outfit"],
        "skills": {"status, laundry_done, states": "M3"},
        "handoff": [],
    }
    default_action = "status"
    RULES = (
        (("done", "clean", "back in", "propre", "fini"), "back"),
        (("lent", "prêté", "lend"), "lend"),
        (("dirty", "put", "sale", "wash", "laver", "in the laundry"), "put"),
        (("what's in", "what is in", "status", "qu'est-ce qui"), "status"),
    )

    def keyword_route(self, message: str) -> str | None:
        m = message.lower()
        if any(w in m for w in ("done", "clean", "back", "propre", "fini")):
            return "back"
        if any(w in m for w in ("lent", "prêté", "borrow")):
            return "lend"
        if any(w in m for w in ("dirty", "put", "sale", "wash", "laver")):
            return "put"
        return "status"

    def actions(self):
        pcs = {"pieces": "piece names, comma separated"}
        return {
            "status": IdeaAction("what is in the laundry / lent now (+ reminders)", self.status),
            "put": IdeaAction("put pieces in the laundry", self.put, pcs),
            "back": IdeaAction(
                "pieces back in the closet (all the laundry if no piece given)", self.back, pcs
            ),
            "lend": IdeaAction("mark pieces as lent to someone", self.lend, {**pcs, "to": "person"}),
        }

    async def status(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        res = await ctx.call("m03_wear_log", "states", {"item_ids": [it["id"] for it in cat["items"]]})
        rows = [r for r in res.get("items", []) if r.get("status") != "available"]
        return {
            "unavailable": [
                {
                    "piece": names_of(cat, [r["item_id"]])[0],
                    "status": r["status"],
                    "since": r.get("status_since"),
                }
                for r in rows
            ],
            "reminders": [names_of(cat, [r["item_id"]])[0] for r in res.get("reminders", [])],
        }

    async def _set(self, ctx: Ctx, a: dict, status: str, **extra) -> dict:
        cat = await ctx.catalog()
        pcs = resolve_pieces(a.get("pieces") or ctx.message, cat["items"])
        if not pcs:
            return {"question": "Which piece?"}
        await ctx.call(
            "m03_wear_log", "status", {"item_ids": [p["id"] for p in pcs], "status": status, **extra}
        )
        return {"done": True, "status": status, "pieces": [p["name"] for p in pcs]}

    async def put(self, ctx: Ctx, a: dict) -> dict:
        return await self._set(ctx, a, "laundry")

    async def lend(self, ctx: Ctx, a: dict) -> dict:
        return await self._set(ctx, a, "lent", lent_to=a.get("to"))

    async def back(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        pcs = resolve_pieces(a.get("pieces") or "", cat["items"]) if a.get("pieces") else []
        await ctx.call("m03_wear_log", "laundry_done", {"item_ids": [p["id"] for p in pcs] if pcs else None})
        return {"done": True, "back_in_closet": [p["name"] for p in pcs] or "all the laundry"}


# =====================================================================================================
class EventLooksAgent(IdeaAgent):
    """Idea: Event countdown looks."""

    CARD = {
        "name": "event_looks",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 idea (M4, M2, weather)",
        "role": "Adds events (wedding, interview...) and prepares looks ahead with a countdown, using the "
        "forecast of the event day.",
        "ideas": ["Event countdown looks"],
        "when_to_use": ["I have a wedding on Saturday", "My upcoming events"],
        "when_not_to_use": ["Today's outfit -> daily_plan"],
        "skills": {"events": "M4", "looks": "M2"},
        "handoff": [],
    }
    default_action = "upcoming"
    RULES = (
        (("upcoming", "my events", "mes événements", "countdown"), "upcoming"),
        (("i have", "j'ai", "add", "ajoute"), "add"),
    )

    def keyword_route(self, message: str) -> str | None:
        return (
            "add"
            if any(w in message.lower() for w in ("i have", "j'ai", "add", "ajoute", "on ", "le "))
            else "upcoming"
        )

    def actions(self):
        return {
            "add": IdeaAction(
                "add an event and prepare its looks",
                self.add,
                {
                    "date": "YYYY-MM-DD",
                    "title": "e.g. Cousin's wedding",
                    "dress_code": "festive | formal | casual",
                },
            ),
            "upcoming": IdeaAction("upcoming events with countdown and prepared looks", self.upcoming),
        }

    async def _looks(self, ctx: Ctx, day: str, dress: str | None) -> list[dict]:
        cat = await ctx.catalog()
        mood = "classy" if (dress or "") in ("formal", "festive") else None
        res = await ctx.call(
            "m02_recommendation",
            "recommend",
            {
                "context": {"occasion": "event", "mood": mood, "date": day},
                "options": {"n": 3},
                **m2_items_payload(cat),
            },
        )
        return [outfit_view(o, cat, m2_names(res)) for o in res.get("outfits", [])]

    async def add(self, ctx: Ctx, a: dict) -> dict:
        title = (a.get("title") or "").strip()
        try:
            day = dt.date.fromisoformat(str(a.get("date"))[:10])
        except ValueError:
            return {"question": "What is the event and on which date (YYYY-MM-DD)?"}
        if not title:
            title = "Event"
        await ctx.call(
            "m04_scheduler",
            "event_add",
            {"date": day.isoformat(), "title": title, "occasion": "event", "dress_code": a.get("dress_code")},
        )
        looks = await self._looks(ctx, day.isoformat(), a.get("dress_code"))
        return {
            "event": title,
            "date": day.isoformat(),
            "days_left": (day - dt.date.today()).days,
            "looks": looks,
        }

    async def upcoming(self, ctx: Ctx, a: dict) -> dict:
        cal = await ctx.call("m04_scheduler", "calendar", {"days": 45})
        out = []
        for e in (cal.get("upcoming") or [])[:3]:
            d = str(e.get("date"))[:10]
            out.append(
                {
                    "event": e.get("title"),
                    "date": d,
                    "days_left": (dt.date.fromisoformat(d) - dt.date.today()).days,
                    "looks": (await self._looks(ctx, d, e.get("dress_code")))[:2],
                }
            )
        return {"events": out} if out else {"events": [], "message": "no event in the next 45 days"}


# =====================================================================================================
class LocalShopsAgent(IdeaAgent):
    """Idea: Local shops shortlist for a missing piece (M7 by BO6, real catalogue of Tunisian shops)."""

    CARD = {
        "name": "local_shops",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 idea (M7 local catalogue)",
        "role": "Shortlists pieces sold by Tunisian shops for a missing piece, a budget in TND and a city.",
        "ideas": ["Local shops shortlist for a missing piece"],
        "when_to_use": ["Where can I buy white sneakers in Tunis under 150 TND?"],
        "when_not_to_use": ["Should I buy this photographed piece -> photo_piece"],
        "skills": {"search": "M7 (FashionCLIP + BM25 + attributes, BO6)"},
        "handoff": [],
    }

    def actions(self):
        return {
            "find": IdeaAction(
                "shops selling a piece (query with colour, type, budget TND, city)",
                self.find,
                {"query": "e.g. white sneakers Tunis 150 TND"},
            )
        }

    async def find(self, ctx: Ctx, a: dict) -> dict:
        query = a.get("query") or ctx.message
        import asyncio

        from modules.m07_local_catalogue import service as m7

        t0 = __import__("time").perf_counter()
        try:
            res = await m7.search({"user_id": ctx.user, "query": query, "session_id": ctx.session})
        except RuntimeError:  # called from a running loop in a worker thread
            res = await asyncio.to_thread(
                lambda: asyncio.run(m7.search({"user_id": ctx.user, "query": query}))
            )
        ctx.note("tool", t0, to="m07_local_catalogue", action="search", ok=True)
        rows = res.get("results", [])
        return {
            "query": query,
            "results": [
                {
                    "shop": r.get("shop"),
                    "item": r.get("item"),
                    "price_tnd": r.get("price_tnd"),
                    "city": r.get("area"),
                    "match": r.get("match"),
                    "url": r.get("product_url"),
                }
                for r in rows[:5]
            ],
            "question": res.get("question") if not rows else None,
        }


# =====================================================================================================
def _encode_photo(path: str) -> dict:
    """Photo of a piece -> FashionCLIP item vector + zero-shot type / colour (same encoder as M2)."""
    from PIL import Image

    from modules.m02_recommendation.engine import encoder

    im = Image.open(path).convert("RGB")
    img = encoder.embed_images([im])[0]
    types = {
        "t-shirt": "top",
        "shirt": "top",
        "sweater": "top",
        "hoodie": "top",
        "jacket": "outerwear",
        "coat": "outerwear",
        "pants": "bottom",
        "jeans": "bottom",
        "shorts": "bottom",
        "skirt": "bottom",
        "dress": "dress",
        "sneakers": "shoes",
        "shoes": "shoes",
        "boots": "shoes",
    }
    colours = ["black", "white", "grey", "navy", "blue", "red", "green", "beige", "brown", "pink", "yellow"]
    tv = encoder.embed_texts([f"a photo of a {t}" for t in types])
    cv = encoder.embed_texts([f"a {c} piece of clothing" for c in colours])
    t = list(types)[int(np.argmax(tv @ img))]
    c = colours[int(np.argmax(cv @ img))]
    txt = encoder.embed_texts([f"{c} {t}"])[0]
    return {
        "type": t,
        "category": types[t],
        "colour": c,
        "image_vec": img,
        "embedding": [float(x) for x in np.concatenate([img, txt])],
    }


class PhotoPieceAgent(IdeaAgent):
    """Ideas: Complete the look from a photo · "Should I buy?" in-store screen (M1 / M6 not ready: built
    here)."""

    CARD = {
        "name": "photo_piece",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 ideas (FashionCLIP, M2)",
        "role": "From a photo of a piece: completes the look with the user's clothes, or says Buy / Think "
            "/ Skip "
        "(duplicates in the wardrobe, how many outfits it would make, cost per wear).",
        "ideas": ["Complete the look from a photo", "Should I buy? in-store screen"],
        "when_to_use": ["What goes with this? (photo)", "Should I buy this? (photo)"],
        "when_not_to_use": ["No photo"],
        "skills": {"type / colour / vector": "FashionCLIP zero-shot", "outfits with it": "M2 complete"},
        "handoff": [],
    }
    default_action = "complete_look"
    RULES = (
        (("buy", "acheter", "price", "prix"), "should_buy"),
        (("goes with", "complete", "va avec"), "complete_look"),
    )

    def keyword_route(self, message: str) -> str | None:
        return (
            "should_buy"
            if any(w in message.lower() for w in ("buy", "acheter", "price", "prix"))
            else "complete_look"
        )

    def actions(self):
        p = {"photo": "path of the uploaded photo"}
        return {
            "complete_look": IdeaAction(
                "outfits with the user's clothes around the photographed piece", self.complete_look, p
            ),
            "should_buy": IdeaAction(
                "Buy / Think / Skip for the photographed piece",
                self.should_buy,
                {**p, "price_tnd": "price in TND"},
            ),
        }

    async def _with_piece(self, ctx: Ctx, a: dict) -> tuple[dict, dict, list[dict], dict]:
        path = a.get("photo") or ctx.state.get("last_photo")
        if not path or not os.path.exists(str(path)):
            raise ValueError("send a photo of the piece first")
        ctx.remember(last_photo=path)
        import asyncio
        import time

        t0 = time.perf_counter()
        piece = await asyncio.to_thread(_encode_photo, path)
        ctx.note(
            "tool",
            t0,
            to="fashionclip",
            action="encode_photo",
            ok=True,
            type=piece["type"],
            colour=piece["colour"],
        )
        cat = await ctx.catalog()
        items = list(cat.get("m2_items") or [])
        new = {
            "item_id": "photo_piece",
            "user_id": ctx.user,
            "image_raw": str(path),
            "category": piece["category"],
            "subcategory": piece["type"],
            "colors": [{"name": piece["colour"], "hex": "#808080", "share": 1.0}],
            "embedding": piece["embedding"],
        }
        res = await ctx.call(
            "m02_recommendation",
            "complete",
            {
                "pinned_item_ids": ["photo_piece"],
                "items": items + [new],
                "context": {"occasion": "casual"},
                "options": {"n": 5},
            },
        )
        names = {**m2_names(res), "photo_piece": f"the new {piece['colour']} {piece['type']}"}
        outs = [outfit_view(o, cat, names) for o in res.get("outfits", [])]
        return piece, cat, outs, items

    async def complete_look(self, ctx: Ctx, a: dict) -> dict:
        piece, cat, outs, _ = await self._with_piece(ctx, a)
        return {"piece": f"{piece['colour']} {piece['type']}", "outfits": outs[:3]}

    async def should_buy(self, ctx: Ctx, a: dict) -> dict:
        piece, cat, outs, items = await self._with_piece(ctx, a)
        sims = []
        for it in items:
            if it.get("category") == piece["category"] and it.get("embedding"):
                v = np.asarray(it["embedding"][:512], np.float32)
                sims.append((float(v @ piece["image_vec"] / (np.linalg.norm(v) + 1e-9)), it["item_id"]))
        sims.sort(reverse=True)
        dup = [s for s in sims if s[0] > 0.9]
        good = [o for o in outs if o["score"] >= 0.6]
        verdict = "Skip" if dup else ("Buy" if len(good) >= 3 else "Think")
        price = a.get("price_tnd")
        cpw = None
        try:
            if price:
                cpw = round(float(price) / max(1, 10 * len(good)), 1)  # ~10 wears per good outfit in a year
        except (TypeError, ValueError):
            cpw = None
        return {
            "piece": f"{piece['colour']} {piece['type']}",
            "verdict": verdict,
            "similar_owned": [names_of(cat, [i])[0] for _, i in dup[:3]],
            "good_outfits_with_it": len(good),
            "examples": [o["pieces"] for o in good[:2]],
            "cost_per_wear_tnd": cpw,
        }


# =====================================================================================================
class DeclutterAgent(IdeaAgent):
    """Idea: Declutter suggestions (M1 not ready: wear stats from M3 + near-duplicates by FashionCLIP)."""

    CARD = {
        "name": "declutter",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 idea (M3, FashionCLIP)",
        "role": "Suggests what to donate or sell: never / rarely worn pieces and near-duplicates.",
        "ideas": ["Declutter suggestions"],
        "when_to_use": ["What can I get rid of?", "Clean my wardrobe"],
        "when_not_to_use": ["What to wear"],
        "skills": {"wear stats": "M3", "duplicates": "FashionCLIP vectors"},
        "handoff": [],
    }

    def actions(self):
        return {"suggest": IdeaAction("pieces to donate / sell, with the reason", self.suggest)}

    async def suggest(self, ctx: Ctx, a: dict) -> dict:
        cat = await ctx.catalog()
        st = await ctx.call("m03_wear_log", "stats", {"item_ids": [it["id"] for it in cat["items"]]})
        rows = {r["item_id"]: r for r in st.get("items", [])}
        never = [i for i, r in rows.items() if not r.get("wear_count")]
        rare = [i for i, r in rows.items() if r.get("wear_count") and not r.get("wears_90d")]
        dups = []
        items = [it for it in cat.get("m2_items") or [] if it.get("embedding")]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a_, b_ = items[i], items[j]
                if a_["category"] != b_["category"]:
                    continue
                va, vb = np.asarray(a_["embedding"][:512]), np.asarray(b_["embedding"][:512])
                if float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9)) > 0.93:
                    wa = rows.get(a_["item_id"], {}).get("wear_count", 0)
                    wb = rows.get(b_["item_id"], {}).get("wear_count", 0)
                    keep, drop = (a_, b_) if wa >= wb else (b_, a_)
                    dups.append(
                        {
                            "keep": names_of(cat, [keep["item_id"]])[0],
                            "let_go": names_of(cat, [drop["item_id"]])[0],
                        }
                    )
        return {
            "never_worn": names_of(cat, never)[:8],
            "not_worn_in_90_days": names_of(cat, rare)[:8],
            "near_duplicates": dups[:5],
            "pieces_total": len(cat["items"]),
        }


# =====================================================================================================
class BO2Orchestrator(BOOrchestrator):
    """BO2 agent: Time optimisation (and the "Quick natural-language request" idea)."""

    CARD = {
        "name": "time_optimisation",
        "version": "1.0.0",
        "owner": "BO2",
        "module": "BO2 orchestrator",
        "role": "Time optimisation agent: understands a quick request and hands it to the right BO2 idea "
            "agent "
        "(prepared outfit of today / tomorrow, one-tap swap, laundry, event looks, local shops, photo of a "
        "piece, declutter, packing).",
        "ideas": ["all BO2 ideas", "Quick natural-language request"],
        "when_to_use": ["anything that saves time in the morning"],
        "when_not_to_use": ["explaining / exploring outfits -> personalised_recommendations"],
        "skills": {},
        "handoff": [],
    }
    default_action = "daily_plan"
    IDEAS = (
        "daily_plan",
        "swap",
        "laundry",
        "event_looks",
        "local_shops",
        "photo_piece",
        "declutter",
        "travel",
    )
    PARTNER = "personalised_recommendations"
    PARTNER_IDEAS = (
        "daily_outfit",
        "rotation",
        "forgotten",
        "capsule",
        "seasonal_refresh",
        "avatar_preview",
        "gap_filling",
        "style_insights",
    )
    RULES = (
        (("laundry", "lessive", "dirty", " sale", "washed", "lent", "prêté"), "laundry"),
        (("change the shoes", "swap", "other shoes", "autres chaussures", "change the top"), "swap"),
        (("haven't worn", "forgot", "oubli", "long time"), "personalised_recommendations:forgotten"),
        (("why", "pourquoi"), "personalised_recommendations:daily_outfit"),
        (("pack", "trip", "travel", "voyage", "valise", "je pars"), "travel"),
        (("wedding", "mariage", "interview", "event", "soirée"), "event_looks"),
        (("tnd", "shop", "boutique", "magasin", "where can i buy"), "local_shops"),
        (("photo", "picture"), "photo_piece"),
        (("donate", "get rid", "declutter", "trier"), "declutter"),
        (("widget", "notification", "today", "aujourd'hui", "tomorrow", "demain"), "daily_plan"),
    )


UPLOADS = Path(__file__).parent / ".uploads"

AGENTS = [
    DailyPlanAgent(),
    SwapAgent(),
    LaundryAgent(),
    EventLooksAgent(),
    LocalShopsAgent(),
    PhotoPieceAgent(),
    DeclutterAgent(),
    BO2Orchestrator(),
]

_ = (OCCASIONS,)
