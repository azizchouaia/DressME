"""Retrieve shop notes for a request. The list is the stand-in for the shop database."""

from __future__ import annotations

import json
import re
from pathlib import Path

_WORDS = re.compile(r"[a-z0-9]+")


def load_shops(path: Path | None = None) -> list[dict]:
    source = path or Path(__file__).with_name("shops.json")
    return json.loads(source.read_text(encoding="utf-8"))


def retrieve_shops(query: str, shops: list[dict] | None = None, limit: int = 2) -> list[dict]:
    """Bag-of-words retrieval. Swap the list for the real shop catalogue without changing the caller."""

    catalog = shops if shops is not None else load_shops()
    needles = set(_WORDS.findall(query.lower()))
    if not needles:
        return []
    ranked: list[tuple[int, dict]] = []
    for shop in catalog:
        hay = set(_WORDS.findall(" ".join(shop.get("styles", []) + [shop.get("note", ""), shop.get("name", "")])))
        score = len(needles & hay)
        if score:
            ranked.append((score, shop))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {"id": shop["id"], "name": shop["name"], "city": shop["city"], "why": shop["note"]}
        for _, shop in ranked[:limit]
    ]


def shop_sentence(hits: list[dict]) -> str:
    if not hits:
        return ""
    parts = [f"{hit['name']} in {hit['city']} ({hit['why']})" for hit in hits]
    return "Shops that carry this kind of look: " + "; ".join(parts) + "."
