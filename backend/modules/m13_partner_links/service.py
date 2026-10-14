"""M13 — Partner commerce links (Tunisian shops, TND, promo codes)."""

import json
from pathlib import Path


def load(data_dir: Path) -> list[dict]:
    p = data_dir / "partners.json"
    return json.loads(p.read_text(encoding="utf-8"))["shops"] if p.exists() else []


def links(shops: list[dict], subcategory: str, colour: str, max_price: float | None, k: int = 3) -> list[dict]:
    out = []
    for s in shops:
        for it in s["items"]:
            if it["subcategory"] != subcategory:
                continue
            if max_price and it["price_tnd"] > max_price * 1.2:
                continue
            rank = (it["colour"] == colour, -it["price_tnd"])
            out.append((rank, {"shop": s["name"], "item": it["name"], "price_tnd": it["price_tnd"],
                               "url": it["url"], "promo_code": s.get("promo_code"),
                               "subcategory": it["subcategory"], "colour": it["colour"]}))
    out.sort(key=lambda x: x[0], reverse=True)
    return [o for _, o in out[:k]]


def typical_prices(shops: list[dict]) -> dict:
    """Median price per type across partner shops (used to judge if a price is fair)."""
    by = {}
    for s in shops:
        for it in s["items"]:
            by.setdefault(it["subcategory"], []).append(it["price_tnd"])
    return {k: sorted(v)[len(v) // 2] for k, v in by.items()}
