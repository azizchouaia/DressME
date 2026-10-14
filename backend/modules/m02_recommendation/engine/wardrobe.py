"""The pieces M2 works with: from the request (M1 format) or, until M1 is live, from the demo wardrobes."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from . import artifacts

SLOT_OF = {
    "top": "top",
    "bottom": "bottom",
    "dress": "dress",
    "outerwear": "outerwear",
    "shoes": "shoes",
    "accessory": "accessory",
    "traditional": "dress",
    "bag": "bag",
}


@dataclass
class Item:
    item_id: str
    category: str
    emb: np.ndarray
    subcategory: str | None = None
    colors: list[dict] = field(default_factory=list)
    pattern: str | None = None
    image: str | None = None
    status: str = "available"
    last_worn: dt.date | None = None
    wear_count: int = 0
    attrs: dict[str, float] = field(default_factory=dict)  # filled by the attribute scorer
    cir: np.ndarray | None = None  # OutfitTransformer-CIR retrieval vector, filled by the recommender

    @property
    def image_emb(self) -> np.ndarray:
        """FashionCLIP image half of the item vector."""
        return self.emb[:512]

    @property
    def slot(self) -> str:
        return SLOT_OF.get(self.category, "accessory")

    @property
    def colour(self) -> str:
        return self.colors[0]["name"] if self.colors else ""

    @property
    def name(self) -> str:
        return " ".join(x for x in (self.colour, self.subcategory or self.category) if x)

    def public(self) -> dict:
        return {
            "item_id": self.item_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "colors": self.colors,
            "pattern": self.pattern,
            "image": self.image,
            "status": self.status,
            "name": self.name,
            "last_worn": self.last_worn.isoformat() if self.last_worn else None,
            "wear_count": self.wear_count,
            "attrs": {k: round(v, 2) for k, v in self.attrs.items()},
        }


def from_payload(items: list) -> list[Item]:
    out = []
    for g in items:
        if not g.embedding:
            continue  # M1 always sends the vector; a piece without one cannot be scored
        e = np.asarray(g.embedding, np.float32)
        if len(e) != 1024:
            continue  # expected [FashionCLIP image 512 | FashionCLIP text 512]
        e = np.concatenate(
            [e[:512] / (np.linalg.norm(e[:512]) + 1e-12), e[512:] / (np.linalg.norm(e[512:]) + 1e-12)]
        )
        out.append(
            Item(
                item_id=g.item_id,
                category=g.category.value,
                emb=e,
                subcategory=g.subcategory,
                colors=[c.model_dump() for c in g.colors],
                pattern=g.pattern,
                image=g.image_cutout or g.image_raw,
                status=g.status,
                last_worn=g.last_worn,
                wear_count=g.wear_count,
            )
        )
    return out


@lru_cache(maxsize=1)
def _demo_catalogue() -> tuple[dict[str, dict], np.ndarray, dict[str, int], dict[str, list[str]]]:
    items = json.load(open(artifacts.WARDROBE_ITEMS))
    emb = np.load(artifacts.WARDROBE_EMB)
    demo = json.load(open(artifacts.DEMO_WARDROBES))
    return {it["item_id"]: it for it in items}, emb, {it["item_id"]: k for k, it in enumerate(items)}, demo


def demo_users() -> list[str]:
    return list(_demo_catalogue()[3])


def demo_wear_log(user_id: str, items: list[Item], today: dt.date, days: int = 120) -> list[dict]:
    """Synthetic wear log for the demo users (stand-in for M3): a few favourites are worn a lot,
    about a quarter of the wardrobe is never worn in the last 2 months (forgotten pieces)."""
    import random

    rng = random.Random(f"{user_id}-wear")
    by_slot: dict[str, list[Item]] = {}
    for it in items:
        by_slot.setdefault(it.slot, []).append(it)
    weights = {it.item_id: rng.choice([12, 5, 1, 0.5, 0.2]) for it in items}
    dormant = {it.item_id for it in rng.sample(items, len(items) // 4)}
    log = []
    for d in range(days, 0, -1):
        if rng.random() < 0.15:
            continue
        day = today - dt.timedelta(days=d)
        recent = d <= 70

        def pick(slot, recent=recent):
            pool = [i for i in by_slot.get(slot, []) if not (recent and i.item_id in dormant)]
            return rng.choices(pool, [weights[i.item_id] for i in pool])[0] if pool else None

        if by_slot.get("dress") and rng.random() < 0.2:
            outfit = [pick("dress"), pick("shoes")]
        else:
            outfit = [pick("top"), pick("bottom"), pick("shoes")]
        if rng.random() < 0.35:
            outfit.append(pick("outerwear"))
        log.append({"date": day, "item_ids": [i.item_id for i in outfit if i]})
    return log


def load_demo(user_id: str | None) -> list[Item]:
    meta, emb, row, demo = _demo_catalogue()
    ids = demo.get(user_id or "", demo.get("demo_f"))
    out = []
    for iid in ids:
        m = meta[iid]
        out.append(
            Item(
                item_id=iid,
                category=m["category"],
                emb=emb[row[iid]],
                subcategory=m["subcategory"],
                colors=m["colors"],
                pattern=m["pattern"],
                image=f"/m02/demo/img/{m['image']}.jpg",
            )
        )
    return out
