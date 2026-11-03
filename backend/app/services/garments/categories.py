"""Map a photo classification onto a wardrobe category that has an outfit slot."""

from __future__ import annotations

# Confidence below this is too close to a guess, so the saved category stays put.
MIN_CONFIDENCE = 0.18

# These are the categories the avatar can wear. "other" and "accessory" have no slot.
SLOT_LABELS: dict[str, str] = {
    "t-shirt": "Top",
    "shirt": "Top",
    "dress": "Top",
    "pants": "Bottom",
    "jeans": "Bottom",
    "jacket": "Outerwear",
    "shoes": "Shoes",
}


def category_from_classification(category: str | None, confidence: float) -> str | None:
    """Return a wearable category, or None when the photo is not a clear garment."""
    if category not in SLOT_LABELS or confidence < MIN_CONFIDENCE:
        return None
    return category


def ready_message(category: str | None) -> str:
    slot = SLOT_LABELS.get(category or "")
    if slot is None:
        return "3D preview is ready. Open Avatar to try this piece on."
    return f"3D preview is ready. Saved as a {category}, so it shows under {slot}."
