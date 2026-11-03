"""Run one stylist conversation against the demo wardrobe.

Uses FashionCLIP for the clothing vectors and Groq for the spoken reply.
Reads LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL from the repo .env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from recommender.assistant import Stylist
from recommender.engine import Conditions, EventLog, Piece
from recommender.fashionclip import FashionCLIP

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(__file__).with_name("demo_wardrobe.json")


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def wardrobe(embedder: FashionCLIP) -> list[Piece]:
    pieces = []
    for raw in json.loads(CATALOG.read_text(encoding="utf-8")):
        pieces.append(
            Piece(
                id=raw["id"],
                name=raw["name"],
                category=raw["category"],
                vector=embedder.embed_text(raw["text"]),
                size=raw["size"],
                price=float(raw["price"]),
                stock=int(raw["stock"]),
            )
        )
    return pieces


def show(title: str, turn, lines: list[str]) -> None:
    lines.append(f"=== {title} ===")
    lines.append(turn.reply)
    if turn.outfit:
        lines.append("Outfit:")
        for item in turn.outfit.pieces:
            lines.append(f"  {item.piece.slot}: {item.piece.name} ({item.score:.2f})")
    if turn.shops:
        lines.append("Shops: " + ", ".join(shop["name"] for shop in turn.shops))
    lines.append("")
    if turn.outfit:
        print("Outfit:")
        for item in turn.outfit.pieces:
            print(f"  {item.piece.slot}: {item.piece.name} ({item.score:.2f})")
    if turn.shops:
        print("Shops:", ", ".join(shop["name"] for shop in turn.shops))


def main() -> None:
    load_env()
    embedder = FashionCLIP()
    pieces = wardrobe(embedder)
    stylist = Stylist(embedder, EventLog(ROOT / "storage" / "stylist-demo"))
    conditions = Conditions(weather="rainy", season="autumn", occasion="office", size="M", budget=120)
    lines: list[str] = []
    first = stylist.chat(
        "demo",
        pieces,
        "What should I wear to the office? It is raining.",
        conditions,
        llm_base_url=os.environ.get("LLM_BASE_URL", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", ""),
    )
    show("Rainy office", first, lines)
    second = stylist.chat(
        "demo",
        pieces,
        "I love the olive rain jacket",
        conditions,
        llm_base_url=os.environ.get("LLM_BASE_URL", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", ""),
    )
    show("After a like", second, lines)
    report = ROOT / "storage" / "stylist-demo" / "demo.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
