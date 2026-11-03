"""Map wardrobe rows onto the stylist and keep FashionCLIP off the import path."""

from __future__ import annotations

import sys
from pathlib import Path

from app.models.clothing_item import ClothingItem
from app.services.storage import get_storage

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from recommender.assistant import Stylist, Turn  # noqa: E402
from recommender.engine import Conditions, EventLog, Piece  # noqa: E402


def _description(item: ClothingItem) -> str:
    parts = [item.color, item.secondary_color, item.sleeve_type, item.pattern, item.material, item.category, item.name]
    return " ".join(part for part in parts if part)


def pieces_from_items(items: list[ClothingItem], embedder) -> list[Piece]:
    storage = get_storage()
    pieces: list[Piece] = []
    for item in items:
        if item.image_key:
            vector = embedder.embed_image(storage.read(item.image_key))
        else:
            vector = embedder.embed_text(_description(item))
        price = None
        stock = 1
        if item.garment_measurements:
            raw_price = item.garment_measurements.get("price")
            raw_stock = item.garment_measurements.get("stock")
            price = float(raw_price) if raw_price is not None else None
            stock = int(raw_stock) if raw_stock is not None else 1
        pieces.append(
            Piece(
                id=str(item.id),
                name=item.name,
                category=item.category,
                vector=vector,
                size=item.size,
                price=price,
                stock=stock,
            )
        )
    return pieces


def advise(
    user_id: str,
    items: list[ClothingItem],
    message: str,
    weather: str,
    season: str,
    occasion: str,
    size: str,
    budget: float | None,
    image: bytes | None,
    data_dir: Path,
    llm_base_url: str,
    llm_api_key: str,
    llm_model: str,
    embedder=None,
) -> Turn:
    if embedder is None:
        from recommender.fashionclip import FashionCLIP

        embedder = FashionCLIP()
    stylist = Stylist(embedder, EventLog(data_dir))
    return stylist.chat(
        user_id,
        pieces_from_items(items, embedder),
        message,
        Conditions(weather=weather, season=season, occasion=occasion, size=size, budget=budget),
        image,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )
