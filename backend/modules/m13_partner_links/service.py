"""M13 — Partner commerce links (Tunisian shops, TND, promo codes).

Shop data, best first:
1. M7 local catalogue (BO6): real Tunisian shops scraped in ml/data/shops/local_catalogue_clean.csv
2. ml/data/bo5/partners.json: fictional shops (offline demo / tests)
Clicks are logged through M7's event log, so BO5 can measure "user went to the shop" (KPI).
"""

import csv
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
M7_CSV = ROOT / "ml" / "data" / "shops" / "local_catalogue_clean.csv"

# M7 subcategory -> Smart Buy type (only the types Smart Buy judges; the rest are skipped)
M7_TYPES = {"tshirt": "t-shirt", "shirt": "shirt", "sweater": "sweater", "jeans": "jeans", "trousers": "trousers",
            "skirt": "skirt", "sneakers": "sneakers", "boots": "boots", "sandals": "sandals", "jacket": "jacket",
            "coat": "coat", "dress": "dress", "traditional": "jebba", "blouse": "blouse", "blazer": "blazer",
            "loafers": "loafers", "chinos": "chinos"}
M7_COLOURS = {"light_blue": "blue", "khaki": "olive", "yellow": "mustard"}


@lru_cache(maxsize=2)
def _m7_shops(path: str) -> tuple:
    by_shop: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sub = M7_TYPES.get(r["subcategory"])
            try:
                price = float(r["price_tnd"])
            except (TypeError, ValueError):
                continue
            if not sub or r.get("available") != "true":
                continue
            s = by_shop.setdefault(r["shop_name"], {"name": r["shop_name"], "city": r.get("city") or None,
                                                    "url": r["shop_url"], "promo_code": None, "items": [],
                                                    "source": "m7"})
            s["items"].append({"name": r["product_name"], "subcategory": sub,
                               "colour": M7_COLOURS.get(r["color"], r["color"]) or None, "price_tnd": price,
                               "url": r["product_url"], "image_url": r["image_url"], "product_id": r["product_id"],
                               "gender": r.get("gender") or None, "sizes": r.get("size") or None})
    return tuple(by_shop.values())


def load(data_dir: Path, source: str = "auto") -> list[dict]:
    """source: auto (M7 if its catalogue is there) | m7 | fictional."""
    if source in ("auto", "m7") and M7_CSV.is_file():
        return [dict(s) for s in _m7_shops(str(M7_CSV))]
    p = data_dir / "partners.json"
    return json.loads(p.read_text(encoding="utf-8"))["shops"] if p.exists() else []


def links(shops: list[dict], subcategory: str, colour: str, max_price: float | None, k: int = 3,
          gender: str | None = None, one_per_shop: bool = False) -> list[dict]:
    out = []
    for s in shops:
        for it in s["items"]:
            if it["subcategory"] != subcategory:
                continue
            if max_price and it["price_tnd"] > max_price * 1.2:
                continue
            if gender and it.get("gender") not in (None, gender, "unisex"):
                continue
            rank = (it["colour"] == colour, -it["price_tnd"])
            out.append((rank, {"shop": s["name"], "city": s.get("city"), "item": it["name"],
                               "price_tnd": it["price_tnd"], "url": it["url"], "promo_code": s.get("promo_code"),
                               "subcategory": it["subcategory"], "colour": it["colour"],
                               "image_url": it.get("image_url"), "product_id": it.get("product_id"),
                               "source": s.get("source", "fictional")}))
    out.sort(key=lambda x: x[0], reverse=True)
    seen, res = set(), []
    for _, o in out:  # one_per_shop: one product per shop, so the user gets a real choice
        if not one_per_shop or o["shop"] not in seen:
            seen.add(o["shop"])
            res.append(o)
        if len(res) == k:
            break
    return res


def typical_prices(shops: list[dict]) -> dict:
    """Median price per type across partner shops (used to judge if a price is fair)."""
    by = {}
    for s in shops:
        for it in s["items"]:
            by.setdefault(it["subcategory"], []).append(it["price_tnd"])
    return {k: sorted(v)[len(v) // 2] for k, v in by.items()}


def log_click(product_id: str, shop: str | None, user_id: str | None, rank: int | None = None,
              search_id: str | None = None) -> bool:
    """Forward a 'went to the shop' click to M7's event log. False when M7 is not available."""
    try:
        from modules.m07_local_catalogue import events
    except ImportError:
        return False
    events.log_click("shop_click", product_id, search_id, shop, rank, user_id)
    return True
