"""Owner: BO7 · what the BO7 sharing features need from the other teams' modules, with mocks until they exist.

Each function asks the owner's module first, through its public function (the same one its HTTP route
serves), and uses a BO7 mock in the agreed shape when the owner has not built it yet (`service.py` still
raises NotImplementedError, or answers the week-1 placeholder `{"todo": ...}`). So when a team ships its
module, BO7 uses the real answer with no code change. Every answer says where it came from:
`source = "M3"` (the owner) or `"mock"` (this file). Nothing in modules/mXX is changed (rule 4).

What BO7 needs from each module (the `result` of their route), also listed in INTEGRATION.md:

  M1  wardrobe (BO3)          items of a user, duplicate groups               (real, in-process)
  M2  recommendation (BO1/2)  /m02/recommend {mode: "match", targets} → {items: [{target, item_id, score}]}
  M3  wear log (BO1/2)        POST /m03/stats {month} → {days_logged, outfits, wears: {item_id: n}}
  M5  style profile (BO4)     POST /m05/profile → {vector: {tag: weight}, tags: [...]}
  M6  smart buy (BO5)         /m06/verdict {candidate} → {verdict, score, similar, new_outfits}
  M11 trip planner (BO3)      /m11/plan {destination, days} → {days: [{day, item_ids}], packing}
  M12 style evolution (BO4)   POST /m12/timeline → {months: [{month, style, main_colour}]}
  M14 stylist mode (BO6)      POST /m14/clients {stylist_id} → {stylists | clients: [{id, name, ...}]}
"""

import hashlib
import importlib
import inspect
from collections import Counter
from datetime import date

from shared.schemas import Garment

ONE_PIECE = {"dress", "traditional"}
SLOTS = ("top", "bottom", "shoes")


# --------------------------------------------------------------------------------------------- helpers
def _seed(*parts: str) -> int:
    """Deterministic pseudo-random number, so a mock gives the same answer every time (testable)."""
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


def _colour(g: Garment) -> tuple[str | None, str | None]:
    if not g.colors:
        return None, None
    c = max(g.colors, key=lambda c: c.share)
    return c.name.lower(), c.hex


def _rgb(hex_: str | None) -> tuple[int, int, int]:
    h = (hex_ or "#888888").lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def colour_distance(a: str | None, b: str | None) -> float:
    """0 (same colour) … 1 (opposite), simple RGB distance."""
    ra, rb = _rgb(a), _rgb(b)
    return (sum((x - y) ** 2 for x, y in zip(ra, rb, strict=True)) ** 0.5) / 441.7


def wardrobe(user_id: str) -> list[Garment]:
    """The user's garments, from M1 (through M15's wardrobe adapter, which already reads M1)."""
    from modules.m15_challenges.singleton import challenges_agent

    return challenges_agent.wardrobe.items(user_id)


def piece(g: Garment) -> dict:
    """A garment as BO7 shows it (tag, card item)."""
    name, hex_ = _colour(g)
    return {
        "item_id": g.item_id,
        "category": g.category.value,
        "label": g.subcategory or g.category.value,
        "image": g.image_cutout or g.image_raw,
        "photo": g.image_raw,
        "color": name,
        "color_hex": hex_,
        "brand": g.local_tag,
        "material": g.material,
        "wear_count": g.wear_count,
    }


def _owner(module: str, fn: str, req: dict) -> dict | None:
    """The owner's answer, or None while it is not built (NotImplementedError / week-1 placeholder)."""
    try:
        router = importlib.import_module(f"modules.{module}.router")
        out = getattr(router._impl(), fn)(req)
        if inspect.isawaitable(out):  # the template routes are sync; an async owner is called over HTTP later
            out.close()
            return None
    except Exception:  # noqa: BLE001 — not built yet, or broken: BO7 keeps working with its mock
        return None
    result = (out or {}).get("result") if isinstance(out, dict) else None
    if not isinstance(result, dict) or not result or "todo" in result:
        return None
    return result


def _answer(module: str, fn: str, req: dict, needs: tuple[str, ...], mock) -> dict:
    real = _owner(module, fn, req)
    if real is not None and all(k in real for k in needs):
        return {**real, "source": module.split("_")[0].upper()}
    return {**mock(), "source": "mock"}


# ------------------------------------------------------------------------------------------- M1 · BO3
async def duplicates(user_id: str) -> dict:
    """Groups of near-identical pieces. Real M1 (`/m01/duplicates`, embeddings) first; when it finds none
    (mock mode has no embeddings), BO7's rule: same category and same main colour."""
    try:
        from modules.m01_wardrobe import service
        from modules.m01_wardrobe.contract import DuplicatesRequest

        res = await service.duplicates(DuplicatesRequest(user_id=user_id))
        if res.groups:
            return {"groups": res.groups, "source": "M1"}
    except Exception:  # noqa: BLE001
        pass
    by: dict[tuple, list[str]] = {}
    for g in wardrobe(user_id):
        by.setdefault((g.category.value, _colour(g)[0]), []).append(g.item_id)
    return {"groups": [ids for ids in by.values() if len(ids) >= 2], "source": "mock"}


# ------------------------------------------------------------------------------------------- M3 · BO1/2
def wear_stats(user_id: str, month: str | None = None) -> dict:
    """How often each piece was worn this month."""
    month = month or date.today().strftime("%Y-%m")
    items = wardrobe(user_id)

    def mock() -> dict:
        wears = {}
        for g in items:
            n = g.wear_count or (_seed(user_id, month, g.item_id) % 7)  # 0..6 wears in the month
            if _seed("unworn", g.item_id) % 5 == 0:  # about one piece in five stays in the closet
                n = 0
            wears[g.item_id] = n
        days = min(30, 12 + _seed(user_id, month) % 15)
        return {"month": month, "days_logged": days, "outfits": days, "wears": wears}

    return _answer(
        "m03_wear_log", "stats", {"user_id": user_id, "payload": {"month": month}}, ("wears",), mock
    )


# ------------------------------------------------------------------------------------------- M6 · BO5
def smartbuy_verdict(user_id: str, candidate: dict) -> dict:
    """Buy / Think / Skip for a piece the user wants to buy (candidate: category, label, color_hex)."""
    items = wardrobe(user_id)

    def mock() -> dict:
        cat = candidate.get("category")
        same = [g for g in items if g.category.value == cat]
        similar = [
            g.item_id for g in same if colour_distance(_colour(g)[1], candidate.get("color_hex")) < 0.18
        ]
        # new outfits it makes: pieces of the complementary slots it can be worn with
        if cat == "top":
            partners = [g for g in items if g.category.value == "bottom"]
        elif cat == "bottom":
            partners = [g for g in items if g.category.value == "top"]
        else:
            partners = [g for g in items if g.category.value in ("top", "bottom")]
        new_outfits = 0 if similar else len(partners)
        score = round(max(0.0, min(1.0, 0.35 + 0.08 * new_outfits - 0.35 * len(similar))), 2)
        verdict = "buy" if score >= 0.7 else "think" if score >= 0.4 else "skip"
        return {"verdict": verdict, "score": score, "similar": similar, "new_outfits": new_outfits}

    return _answer(
        "m06_smartbuy",
        "verdict",
        {"user_id": user_id, "payload": {"candidate": candidate}},
        ("verdict", "score"),
        mock,
    )


# ------------------------------------------------------------------------------------------- M2 · BO1/2
def match_pieces(user_id: str, targets: list[dict]) -> dict:
    """For each target piece (category + colour, e.g. a friend's look), the closest piece the user owns."""
    items = wardrobe(user_id)

    def mock() -> dict:
        out, used = [], set()
        for t in targets:
            cat = t.get("category")
            pool = [
                g
                for g in items
                if g.item_id not in used
                and (g.category.value == cat or (cat in ONE_PIECE and g.category.value in ONE_PIECE))
            ]
            if not pool:
                out.append({"target": t, "item_id": None, "score": 0.0})
                continue
            best = min(pool, key=lambda g: colour_distance(_colour(g)[1], t.get("color_hex")))
            used.add(best.item_id)
            score = round(1 - colour_distance(_colour(best)[1], t.get("color_hex")), 2)
            out.append({"target": t, "item_id": best.item_id, "score": score})
        return {"items": out}

    return _answer(
        "m02_recommendation",
        "recommend",
        {"user_id": user_id, "payload": {"mode": "match", "targets": targets}},
        ("items",),
        mock,
    )


def complete_board(user_id: str, item_ids: list[str]) -> dict:
    """Missing slots of a board (top / bottom / shoes) filled with owned pieces ("complete with AI")."""
    items = wardrobe(user_id)
    chosen = [g for g in items if g.item_id in item_ids]

    def mock() -> dict:
        cats = {g.category.value for g in chosen}
        missing = [s for s in SLOTS if s not in cats and not (s in ("top", "bottom") and cats & ONE_PIECE)]
        main = _colour(chosen[0])[1] if chosen else None
        added = []
        for slot in missing:
            pool = [g for g in items if g.category.value == slot and g.item_id not in item_ids]
            if pool:  # the piece that goes best with the board's first colour (closest neutral match)
                added.append(min(pool, key=lambda g: colour_distance(_colour(g)[1], main)).item_id)
        return {"added": added, "missing": missing}

    return _answer(
        "m02_recommendation",
        "recommend",
        {"user_id": user_id, "payload": {"mode": "complete", "locked_items": item_ids}},
        ("added",),
        mock,
    )


# ------------------------------------------------------------------------------------------- M11 · BO3
def trip_plan(user_id: str, destination: str, days: int) -> dict:
    """One outfit per day with the fewest pieces (pieces are reused, as a packing list should)."""
    items = wardrobe(user_id)

    def mock() -> dict:
        by = {s: sorted([g for g in items if g.category.value == s], key=lambda g: g.item_id) for s in SLOTS}
        k = {
            "top": min(len(by["top"]), max(2, (days + 1) // 2)),
            "bottom": min(len(by["bottom"]), 2),
            "shoes": min(len(by["shoes"]), 1),
        }
        plan = []
        for d in range(days):
            plan.append({"day": d + 1, "item_ids": [by[s][d % k[s]].item_id for s in SLOTS if k[s]]})
        packing = sorted({i for p in plan for i in p["item_ids"]})
        return {"destination": destination, "days": plan, "packing": packing}

    return _answer(
        "m11_trip_planner",
        "plan",
        {"user_id": user_id, "payload": {"destination": destination, "days": days}},
        ("days", "packing"),
        mock,
    )


# ------------------------------------------------------------------------------------------- M12 · BO4
STYLES = ("casual", "minimal", "classic", "street", "traditional", "bold")


def style_timeline(user_id: str, months: int = 4) -> dict:
    """The user's style month by month (M12: monthly style centroid + drift)."""
    items = wardrobe(user_id)

    def mock() -> dict:
        colours = Counter(_colour(g)[0] for g in items if _colour(g)[0])
        main = [c for c, _ in colours.most_common(3)] or ["grey"]
        today = date.today()
        out = []
        for i in range(months - 1, -1, -1):
            y, m = divmod(today.year * 12 + today.month - 1 - i, 12)
            key = f"{y}-{m + 1:02d}"
            style = STYLES[_seed(user_id, key) % len(STYLES)] if i else _current_style(items)
            out.append({"month": key, "style": style, "main_colour": main[i % len(main)]})
        return {"months": out}

    return _answer(
        "m12_style_evolution",
        "timeline",
        {"user_id": user_id, "payload": {"months": months}},
        ("months",),
        mock,
    )


def _current_style(items: list[Garment]) -> str:
    cats = Counter(g.category.value for g in items)
    if cats.get("traditional", 0) >= 3:
        return "traditional"
    dark = sum(1 for g in items if _colour(g)[0] in ("black", "grey", "white", "navy"))
    return "minimal" if dark > len(items) / 2 else "casual"


# ------------------------------------------------------------------------------------------- M5 · BO4
# What each demo user said they like in M5's swipe onboarding (BO4 owns it; stand-in until M5 is built).
# The demo users share the same demo wardrobe, so without this their wardrobe vectors would be identical.
MOCK_TASTES = {
    "usr_042": {"casual": 0.5, "traditional": 0.3, "minimal": 0.2},
    "amen": {"street": 0.5, "casual": 0.3, "sport": 0.2},
    "yasmine": {"traditional": 0.5, "local": 0.3, "bold": 0.2},
    "sarra": {"minimal": 0.5, "classic": 0.3, "casual": 0.2},
    "ines": {"bold": 0.4, "street": 0.4, "local": 0.2},
    "karim": {"classic": 0.6, "minimal": 0.4},
}


def style_profile(user_id: str) -> dict:
    """Style vector of a user: half what they liked in the onboarding swipes, half what their wardrobe holds
    (share of categories, colours and local pieces)."""

    def mock() -> dict:
        tags = Counter()
        try:
            items = wardrobe(user_id)
        except Exception:  # noqa: BLE001 — a user without a wardrobe yet
            items = []
        for g in items:
            tags[g.category.value] += 1
            if _colour(g)[0]:
                tags[_colour(g)[0]] += 1
            if g.local_tag:
                tags["local"] += 1
        total = sum(tags.values()) or 1
        vector = {t: 0.5 * n / total for t, n in tags.items()}
        for t, w in MOCK_TASTES.get(user_id, {}).items():
            vector[t] = vector.get(t, 0.0) + 0.5 * w
        vector = {t: round(v, 4) for t, v in vector.items()}
        taste = sorted(MOCK_TASTES.get(user_id, {}), key=lambda t: -MOCK_TASTES[user_id][t])
        return {"vector": vector, "tags": taste[:3] or [t for t, _ in tags.most_common(3)]}

    return _answer("m05_style_profile", "profile", {"user_id": user_id, "payload": {}}, ("vector",), mock)


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na, nb = sum(v * v for v in a.values()) ** 0.5, sum(v * v for v in b.values()) ** 0.5
    return round(dot / (na * nb), 3) if na and nb else 0.0


# ------------------------------------------------------------------------------------------- M14 · BO6
MOCK_STYLISTS = [
    {
        "stylist_id": "sty_amel",
        "name": "Amel · Atelier Medina",
        "city": "Tunis",
        "speciality": "modern traditional",
    },
    {"stylist_id": "sty_karim", "name": "Karim · Studio K", "city": "Sousse", "speciality": "smart casual"},
]
MOCK_CLIENTS = {
    "sty_amel": [{"client_id": "usr_042", "name": "Omar"}, {"client_id": "yasmine", "name": "Yasmine"}],
    "sty_karim": [{"client_id": "amen", "name": "Amen"}, {"client_id": "usr_042", "name": "Omar"}],
}


def stylists() -> dict:
    return _answer(
        "m14_stylist_mode",
        "clients",
        {"user_id": None, "payload": {"list": "stylists"}},
        ("stylists",),
        lambda: {"stylists": MOCK_STYLISTS},
    )


def clients(stylist_id: str) -> dict:
    return _answer(
        "m14_stylist_mode",
        "clients",
        {"user_id": stylist_id, "payload": {"stylist_id": stylist_id}},
        ("clients",),
        lambda: {"clients": MOCK_CLIENTS.get(stylist_id, [])},
    )
