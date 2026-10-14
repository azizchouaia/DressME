"""M2 pipeline: context -> filter -> slot-based generation (beam search) -> scoring -> ranking -> diversity.

items + context ─► attribute scorer (FashionCLIP zero-shot: warmth, formality, mood)
                ─► hard filters (status, exclusions, extreme weather / formality)
                ─► slot templates (top+bottom+shoes | dress+shoes, + outerwear if the weather asks)
                ─► beam search: for each empty slot the pretrained OutfitTransformer-CIR retrieves the
                    pieces closest to "the ideal missing piece"; partial outfits are pruned with
                    OutfitTransformer-CP (compatibility)
                ─► full score = weighted criteria (compatibility, weather, occasion, mood, taste, novelty)
                                - rotation penalty + forgotten-piece bonus
                ─► diversity (outfits share at most one piece) ─► reasons
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from .wardrobe import Item

OCCASION_FORMALITY = {"work": 0.62, "casual": 0.32, "event": 0.78}
WEIGHTS = {
    "compatibility": 0.30,
    "weather_fit": 0.17,
    "occasion_fit": 0.23,
    "mood_fit": 0.14,
    "style_match": 0.08,
    "novelty": 0.08,
}
REMIX_WEIGHTS = {**WEIGHTS, "compatibility": 0.24, "novelty": 0.30, "occasion_fit": 0.17, "mood_fit": 0.08}
# Typical formality of a garment type (0 = gym wear, 1 = black tie), blended 50/50 with the zero-shot score.
FORMALITY_PRIOR = {
    "t-shirt": 0.15,
    "tee": 0.15,
    "tank top": 0.1,
    "hoodie": 0.05,
    "sweatshirt": 0.1,
    "polo shirt": 0.35,
    "long-sleeve top": 0.35,
    "top": 0.4,
    "knit": 0.45,
    "sweater": 0.4,
    "shirt": 0.7,
    "blouse": 0.7,
    "shorts": 0.1,
    "jeans": 0.3,
    "pants": 0.5,
    "trousers": 0.6,
    "skirt": 0.55,
    "dress": 0.6,
    "jacket": 0.45,
    "coat": 0.6,
    "blazer": 0.85,
    "suit": 0.95,
    "sneakers": 0.15,
    "sandals": 0.2,
    "boots": 0.45,
    "shoes": 0.5,
    "heels": 0.85,
    "loafers": 0.65,
}
# how much each slot counts in the outfit's formality / mood (the top or dress is what people see first)
SLOT_WEIGHT = {"top": 2.0, "dress": 2.5, "bottom": 1.5, "outerwear": 1.2, "shoes": 1.0, "accessory": 0.5}
CORE = ("top", "bottom", "dress")
TEMPLATES = (("top", "bottom", "shoes"), ("dress", "shoes"))
PREFILTER_K = 14  # anchors (first slot) kept per template, by context fit
RETRIEVE_K = 6  # pieces retrieved by CIR per partial outfit and slot
BEAM = 40  # partial outfits kept after each slot
FORGOTTEN_BONUS = 0.04  # added when exactly one piece has not been worn for forgotten_after days


@dataclass
class Ctx:
    occasion: str
    mood: str | None
    temp_c: float
    condition: str
    rainy: bool
    today: dt.date
    rotation_window: int = 7
    forgotten_after: int = 60
    allow_outerwear: bool | None = None
    style_vector: np.ndarray | None = None
    worn_pairs: set = field(default_factory=set)
    has_history: bool = False

    @property
    def target_warmth(self) -> float:
        """Outfit warmth we aim for: 0.15 at 30°C+ ... 0.85 at 6°C and below (zero-shot score scale)."""
        return float(0.15 + 0.7 * np.clip((30 - self.temp_c) / 24, 0, 1))

    @property
    def target_formality(self) -> float:
        return OCCASION_FORMALITY.get(self.occasion, 0.45)

    @property
    def outerwear(self) -> str:
        """required / optional / none."""
        if self.allow_outerwear is not None:
            return "required" if self.allow_outerwear else "none"
        if self.temp_c < 16 or (self.rainy and self.temp_c < 22):
            return "required"
        if self.temp_c >= 24 and not self.rainy:
            return "none"
        return "optional"


def occasion_fit(formality: float, ctx: Ctx) -> float:
    """Event: dressier is never wrong. Casual: too dressy is off. Work: both directions, milder above."""
    t = ctx.target_formality
    if ctx.occasion == "event" and formality >= t:
        return 1.0
    if ctx.occasion == "casual" and formality <= t:
        return 1.0
    if ctx.occasion == "work" and formality > t:
        return gauss(formality, t, 0.3)
    return gauss(formality, t, 0.18)


def shape(outfit) -> str:
    """Outfit shape key, e.g. "bottom+shoes+top"."""
    return "+".join(sorted(i.slot for i in outfit))


def gauss(x: float, mu: float, sd: float) -> float:
    return float(np.exp(-(((x - mu) / sd) ** 2)))


class Recommender:
    def __init__(self, ot, attributes, calibration: dict[str, list[float]] | None = None):
        self.ot = ot  # pretrained OutfitTransformer (CP + CIR)
        self.attributes = attributes  # AttributeScorer (FashionCLIP zero-shot)
        # CP gives higher raw scores to outfits with more pieces (dress+shoes vs top+bottom+shoes+jacket);
        # the raw score is turned into a percentile among random outfits of the same shape.
        self.calibration = {k: np.asarray(v) for k, v in (calibration or {}).items()}

    # ---------------- items ----------------
    def prepare(self, items: list[Item], ctx: Ctx, exclude: set[str]) -> list[Item]:
        if items:
            attrs = self.attributes(np.stack([i.image_emb for i in items]), [i.category for i in items])
            for it, a in zip(items, attrs, strict=True):
                prior = FORMALITY_PRIOR.get((it.subcategory or "").lower())
                if (
                    prior is not None
                ):  # photo says how dressy this piece is, its type says how dressy it can be
                    a["formality"] = 0.5 * a["formality"] + 0.5 * prior
                it.attrs = a
            for it, v in zip(items, self.ot.item_space(np.stack([i.emb for i in items])), strict=True):
                it.cir = v
        out = []
        for it in items:
            if it.status != "available" or it.item_id in exclude:
                continue
            w, f = it.attrs["warmth"], it.attrs["formality"]
            if it.slot in CORE + ("shoes",):
                if ctx.temp_c >= 26 and w > 0.85:
                    continue
                if ctx.temp_c <= 8 and w < 0.15:
                    continue
                if ctx.occasion in ("work", "event") and f < 0.1:
                    continue
            out.append(it)
        return out

    def item_fit(self, it: Item, ctx: Ctx) -> float:
        """Cheap per-piece context score, used to pre-select candidates per slot."""
        s = gauss(it.attrs["formality"], ctx.target_formality, 0.3)
        if it.slot != "outerwear":
            s += gauss(it.attrs["warmth"], ctx.target_warmth, 0.35)
        if ctx.mood in it.attrs:
            s += 0.8 * it.attrs[ctx.mood]
        return s

    # ---------------- scoring ----------------
    def days_since(self, it: Item, ctx: Ctx) -> int | None:
        return (ctx.today - it.last_worn).days if it.last_worn else None

    def breakdown(self, outfit: list[Item], compat: float, ctx: Ctx) -> dict[str, float]:
        core = [i for i in outfit if i.slot in CORE]
        shoes = [i for i in outfit if i.slot == "shoes"]
        outer = [i for i in outfit if i.slot == "outerwear"]
        cw = np.mean([i.attrs["warmth"] for i in core]) if core else 0.5
        if shoes:
            cw = 0.85 * cw + 0.15 * shoes[0].attrs["warmth"]
        warmth = cw + (0.25 * outer[0].attrs["warmth"] if outer else 0)
        weather = gauss(warmth, ctx.target_warmth, 0.25)
        if ctx.rainy and outer:
            weather = min(1.0, weather + 0.1)
        sw = [SLOT_WEIGHT.get(i.slot, 1.0) for i in outfit]
        f = [i.attrs["formality"] for i in outfit]
        # weighted mean, pulled toward the least formal piece: a t-shirt spoils an evening outfit
        if ctx.target_formality >= 0.5:
            formality = 0.65 * float(np.average(f, weights=sw)) + 0.35 * min(f)
        else:  # casual: a single very formal piece looks off
            formality = 0.65 * float(np.average(f, weights=sw)) + 0.35 * max(f)
        mood = (
            float(np.average([i.attrs[ctx.mood] for i in outfit], weights=sw))
            if ctx.mood in ("comfy", "bold", "classy")
            else 0.5
        )
        if ctx.style_vector is not None:
            m = np.mean([i.emb if len(ctx.style_vector) == len(i.emb) else i.image_emb for i in outfit], 0)
            cos = float(m @ ctx.style_vector / (np.linalg.norm(m) * np.linalg.norm(ctx.style_vector) + 1e-9))
            style = float(np.clip((cos - 0.2) / 0.6, 0, 1))
        else:
            style = 0.5
        if ctx.has_history:
            pairs = list(combinations(sorted(i.item_id for i in outfit), 2))
            novelty = sum(p not in ctx.worn_pairs for p in pairs) / max(1, len(pairs))
        else:
            novelty = 0.5
        rotation = 0.0
        if ctx.rotation_window:
            for i in outfit:
                d = self.days_since(i, ctx)
                if d is not None and d < ctx.rotation_window:
                    rotation = max(rotation, 0.25 * (1 - d / ctx.rotation_window))
        forgotten = 0.0
        if ctx.forgotten_after:
            dormant = [i for i in outfit if (self.days_since(i, ctx) or 0) >= ctx.forgotten_after]
            forgotten = FORGOTTEN_BONUS if len(dormant) == 1 else 0.0
        return {
            "compatibility": float(compat),
            "weather_fit": weather,
            "occasion_fit": occasion_fit(formality, ctx),
            "mood_fit": mood,
            "style_match": style,
            "novelty": float(novelty),
            "rotation_penalty": rotation,
            "forgotten_bonus": forgotten,
        }

    @staticmethod
    def total(b: dict[str, float], weights: dict[str, float]) -> float:
        return sum(w * b[k] for k, w in weights.items()) - b["rotation_penalty"] + b["forgotten_bonus"]

    def compat_scores(self, outfits: list[list[Item]], calibrated: bool = False) -> np.ndarray:
        raw = self.ot.compatibility([np.stack([i.emb for i in o]) for o in outfits])
        if not calibrated or not self.calibration:
            return raw
        out = raw.copy()
        for k, o in enumerate(outfits):
            q = self.calibration.get(shape(o))
            if q is not None:
                out[k] = np.searchsorted(q, raw[k]) / len(q)
        return out

    def retrieve(self, partials: list[list[Item]], pool: list[Item], k: int = RETRIEVE_K) -> list[list[Item]]:
        """CIR: for each partial outfit, the k pool pieces nearest to the predicted missing piece."""
        if not partials[0]:
            return [[p] for p in pool]
        q = self.ot.query([np.stack([i.emb for i in p]) for p in partials])
        space = np.stack([i.cir for i in pool])
        out = []
        for p, qv in zip(partials, q, strict=True):
            d = np.linalg.norm(space - qv, axis=1)
            out += [p + [pool[j]] for j in np.argsort(d)[:k]]
        return out

    # ---------------- generation ----------------
    def templates(
        self, ctx: Ctx, by_slot: dict[str, list[Item]], pinned: list[Item]
    ) -> list[tuple[str, ...]]:
        pinned_slots = {i.slot for i in pinned}
        out = []
        for t in TEMPLATES:
            if "dress" in pinned_slots and "dress" not in t:
                continue
            if pinned_slots & {"top", "bottom"} and "dress" in t:
                continue
            if any(not by_slot.get(s) and s not in pinned_slots for s in t):
                continue
            mode = "required" if "outerwear" in pinned_slots else ctx.outerwear
            if mode in ("required", "optional") and (by_slot.get("outerwear") or "outerwear" in pinned_slots):
                out.append(t + ("outerwear",))
            if mode in ("none", "optional") or not (by_slot.get("outerwear") or "outerwear" in pinned_slots):
                out.append(t)
        return out

    def beam(
        self,
        slots: tuple[str, ...],
        fixed: dict[str, Item],
        cands: dict[str, list[Item]],
        ctx: Ctx,
        width: int = BEAM,
    ) -> list[list[Item]]:
        partials: list[list[Item]] = [list(fixed.values())]
        for s in slots:
            if s in fixed:
                continue
            if not cands.get(s):
                return []
            nxt = self.retrieve(partials, cands[s])
            if len(nxt) > width and len(nxt[0]) >= 2:
                comp = self.compat_scores(nxt)
                fit = np.array([np.mean([self.item_fit(i, ctx) for i in o]) for o in nxt])
                keep = np.argsort(-(comp + 0.4 * fit))[:width]
                nxt = [nxt[k] for k in keep]
            partials = nxt
        return partials

    def rank(self, outfits: list[list[Item]], ctx: Ctx, weights: dict[str, float]) -> list[dict]:
        seen, uniq = set(), []
        for o in outfits:
            k = frozenset(i.item_id for i in o)
            if k not in seen:
                seen.add(k)
                uniq.append(o)
        if not uniq:
            return []
        comp = self.compat_scores(uniq, calibrated=True)
        scored = []
        for o, c in zip(uniq, comp, strict=True):
            b = self.breakdown(o, c, ctx)
            scored.append({"items": o, "breakdown": b, "score": self.total(b, weights)})
        return sorted(scored, key=lambda r: -r["score"])

    @staticmethod
    def diverse(ranked: list[dict], n: int, max_shared: int = 1, avoid: set[str] | None = None) -> list[dict]:
        picked: list[dict] = []
        for r in ranked:
            ids = {i.item_id for i in r["items"]}
            if avoid and len(ids & avoid) > max_shared:
                continue
            if all(len(ids & {i.item_id for i in p["items"]}) <= max_shared for p in picked):
                picked.append(r)
            if len(picked) == n:
                break
        if len(picked) < n:  # small wardrobe: relax diversity rather than return too few
            for r in ranked:
                if r not in picked:
                    picked.append(r)
                if len(picked) == n:
                    break
        return picked

    # ---------------- public operations ----------------
    def _split(self, items: list[Item], ctx: Ctx, pinned: list[Item]) -> dict[str, list[Item]]:
        by_slot: dict[str, list[Item]] = {}
        for it in items:
            if it not in pinned:
                by_slot.setdefault(it.slot, []).append(it)
        for s in by_slot:
            by_slot[s] = sorted(by_slot[s], key=lambda i: -self.item_fit(i, ctx))[:PREFILTER_K]
        return by_slot

    def recommend(
        self, items: list[Item], ctx: Ctx, n: int = 3, remix: bool = False, avoid: set[str] | None = None
    ) -> list[dict]:
        by_slot = self._split(items, ctx, [])
        outfits = [o for t in self.templates(ctx, by_slot, []) for o in self.beam(t, {}, by_slot, ctx)]
        ranked = self.rank(outfits, ctx, REMIX_WEIGHTS if remix else WEIGHTS)
        return self.diverse(ranked, n, avoid=avoid)

    def complete(self, items: list[Item], ctx: Ctx, pinned: list[Item], n: int = 3) -> list[dict]:
        by_slot = self._split(items, ctx, pinned)
        fixed = {i.slot: i for i in pinned}
        outfits = [o for t in self.templates(ctx, by_slot, pinned) for o in self.beam(t, fixed, by_slot, ctx)]
        ranked = [r for r in self.rank(outfits, ctx, WEIGHTS) if all(p in r["items"] for p in pinned)]
        return self.diverse(ranked, n, max_shared=len(pinned) + 1)

    def swap(self, items: list[Item], ctx: Ctx, current: list[Item], slot: str, n: int = 5) -> list[dict]:
        keep = [i for i in current if i.slot != slot]
        old = {i.item_id for i in current if i.slot == slot}
        cands = [i for i in items if i.slot == slot and i.item_id not in old]
        ranked = self.rank([keep + [c] for c in cands], ctx, WEIGHTS)
        return ranked[:n]

    def score(self, outfits: list[list[Item]], ctx: Ctx) -> list[dict]:
        comp = self.compat_scores(outfits, calibrated=True) if outfits else []
        return [
            {"items": o, "breakdown": (b := self.breakdown(o, c, ctx)), "score": self.total(b, WEIGHTS)}
            for o, c in zip(outfits, comp, strict=True)
        ]


# ---------------- explanation ----------------
def reasons(r: dict, ctx: Ctx) -> list[str]:
    b, items = r["breakdown"], r["items"]
    out: list[tuple[float, str]] = []
    names = ", ".join(i.name for i in items)
    if b["compatibility"] >= 0.6:
        out.append(
            (WEIGHTS["compatibility"] * b["compatibility"], f"The pieces work well together ({names})")
        )
    outer = next((i for i in items if i.slot == "outerwear"), None)
    if b["weather_fit"] >= 0.6:
        txt = f"Right warmth for {ctx.temp_c:.0f}°C"
        if ctx.rainy and outer:
            txt += f", and the {outer.name} covers the {ctx.condition}"
        out.append((WEIGHTS["weather_fit"] * b["weather_fit"], txt))
    if b["occasion_fit"] >= 0.6:
        out.append((WEIGHTS["occasion_fit"] * b["occasion_fit"], f"The formality level suits {ctx.occasion}"))
    if ctx.mood and b["mood_fit"] >= 0.55:
        out.append((WEIGHTS["mood_fit"] * b["mood_fit"], f"It matches a {ctx.mood} mood"))
    if ctx.style_vector is not None and b["style_match"] >= 0.6:
        out.append((WEIGHTS["style_match"] * b["style_match"], "It is close to the looks you usually like"))
    if ctx.has_history and b["novelty"] >= 0.99:
        out.append((0.05, "You have never worn these pieces together"))
    if b["forgotten_bonus"]:
        it = max(items, key=lambda i: (ctx.today - i.last_worn).days if i.last_worn else -1)
        out.append(
            (1.0, f"It brings back your {it.name}, not worn for {(ctx.today - it.last_worn).days} days")
        )
    return [t for _, t in sorted(out, key=lambda x: -x[0])]


def to_outfit(r: dict, ctx: Ctx, user_id: str | None, source: str = "m02") -> dict:
    b = r["breakdown"]
    why = reasons(r, ctx)
    dormant = [
        i
        for i in r["items"]
        if b["forgotten_bonus"] and i.last_worn and (ctx.today - i.last_worn).days >= ctx.forgotten_after
    ]
    return {
        "outfit_id": uuid.uuid4().hex[:12],
        "user_id": user_id or "anonymous",
        "items": [i.item_id for i in r["items"]],
        "slots": {i.slot: i.item_id for i in r["items"]},
        "context": {
            "occasion": ctx.occasion,
            "date": ctx.today.isoformat(),
            "weather": {"temp_c": ctx.temp_c, "condition": ctx.condition},
        },
        "scores": {
            "compatibility": round(b["compatibility"], 4),
            "style_match": round(b["style_match"], 4),
            "weather_fit": round(b["weather_fit"], 4),
        },
        "score": round(r["score"], 4),
        "score_breakdown": {k: round(v, 4) for k, v in b.items()},
        "reasons": why,
        "explanation": ". ".join(why[:2]) + "." if why else None,
        "forgotten_item_id": dormant[0].item_id if dormant else None,
        "source": source,
    }
