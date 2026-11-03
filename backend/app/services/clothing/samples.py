"""Starter wardrobe linked to the sample GLB garments served from /models."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.clothing_item import ClothingItem
from app.models.outfit import Outfit

SAMPLE_ITEMS: list[dict[str, str]] = [
    {"key": "black_tshirt", "name": "Black T-shirt", "category": "t-shirt", "color": "black",
     "sleeve_type": "short", "pattern": "plain", "material": "cotton", "size": "M"},
    {"key": "white_tshirt", "name": "White T-shirt", "category": "t-shirt", "color": "white",
     "sleeve_type": "short", "pattern": "plain", "material": "cotton", "size": "M"},
    {"key": "olive_longsleeve", "name": "Olive long-sleeve", "category": "shirt",
     "color": "olive", "sleeve_type": "long", "pattern": "plain", "material": "jersey"},
    {"key": "blue_jeans", "name": "Blue jeans", "category": "jeans", "color": "blue",
     "pattern": "plain", "material": "denim", "size": "32"},
    {"key": "black_jeans", "name": "Black jeans", "category": "jeans", "color": "black",
     "pattern": "plain", "material": "denim", "size": "32"},
    {"key": "sand_shorts", "name": "Sand shorts", "category": "pants", "color": "beige",
     "pattern": "plain", "material": "cotton twill"},
    {"key": "black_jacket", "name": "Black jacket", "category": "jacket", "color": "black",
     "sleeve_type": "long", "pattern": "plain", "material": "nylon"},
    {"key": "white_sneakers", "name": "White sneakers", "category": "shoes", "color": "white",
     "material": "leather", "size": "42"},
    {"key": "black_sneakers", "name": "Black sneakers", "category": "shoes", "color": "black",
     "material": "canvas", "size": "42"},
]


def seed_sample_wardrobe(db: Session, user_id: UUID) -> None:
    items: dict[str, ClothingItem] = {}
    for sample in SAMPLE_ITEMS:
        fields = {k: v for k, v in sample.items() if k != "key"}
        item = ClothingItem(
            user_id=user_id,
            glb_url=f"/models/garments/{sample['key']}.glb",
            status="ready",
            **fields,
        )
        db.add(item)
        items[sample["key"]] = item
    db.flush()

    db.add(
        Outfit(
            user_id=user_id,
            name="Everyday black",
            shirt_id=items["black_tshirt"].id,
            pants_id=items["blue_jeans"].id,
            jacket_id=items["black_jacket"].id,
            shoes_id=items["white_sneakers"].id,
            accessory_ids=[],
        )
    )
