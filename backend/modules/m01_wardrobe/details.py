"""Item details shared by mock.py and service.py: applying the form (PATCH) and finishing an extraction."""

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel

from . import storage
from .contract import (
    DocumentKind,
    DocumentResponse,
    InvalidUpdateError,
    ItemStatus,
    ItemUpdate,
    WardrobeItem,
)
from .pipeline import images

# words that name a piece on French / English receipts, by subcategory (abbreviations included)
LINE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "t-shirt": ("t-shirt", "tshirt", "tee", "ts"),
    "shirt": ("chemise", "chem", "shirt"),
    "linen shirt": ("chemise", "chem", "lin", "linen"),
    "polo shirt": ("polo",),
    "blouse": ("blouse", "chemisier"),
    "sweater": ("pull", "sweater", "maille"),
    "sweatshirt": ("sweat",),
    "hoodie": ("sweat", "capuche", "hoodie"),
    "tank top": ("debardeur", "top"),
    "jeans": ("jean", "denim"),
    "chinos": ("chino",),
    "trousers": ("pantalon", "pant", "trouser"),
    "shorts": ("short", "bermuda"),
    "skirt": ("jupe", "skirt"),
    "dress": ("robe", "dress"),
    "summer dress": ("robe", "dress"),
    "evening dress": ("robe", "soiree"),
    "jacket": ("veste", "blouson", "jacket"),
    "leather jacket": ("blouson", "veste", "cuir", "leather"),
    "denim jacket": ("veste", "jean", "denim"),
    "blazer": ("blazer", "veste"),
    "coat": ("manteau", "coat", "parka"),
    "sneakers": ("basket", "sneaker", "tennis"),
    "loafers": ("mocassin", "loafer"),
    "boots": ("botte", "bottine", "boot"),
    "sandals": ("sandale", "sandal", "nu-pied"),
    "heels": ("escarpin", "talon", "heel"),
    "dress shoes": ("derby", "richelieu", "chaussure"),
    "bag": ("sac", "bag", "cabas", "pochette"),
    "belt": ("ceinture", "belt", "ceint"),
    "sunglasses": ("lunette", "solaire", "sunglass"),
    "hat": ("chapeau", "casquette", "hat"),
    "scarf": ("echarpe", "foulard", "scarf"),
    "watch": ("montre", "watch"),
    "jewelry": ("bijou", "collier", "bracelet", "bague"),
    "jebba": ("jebba", "jebbah", "jbba"),
    "kachabia": ("kachabia", "kachabiya"),
    "sefsari": ("sefsari", "safsari"),
    "blouza": ("blouza",),
}


def _plain(text: str) -> str:
    """lowercase, no accents: 'Chemise LIN Marine' -> 'chemise lin marine'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _score(words: set[str], keywords: tuple[str, ...]) -> int:
    """Keywords found in a receipt line; long keywords also match as a prefix (CHEMIS -> chemise)."""
    return sum(1 for k in keywords if k in words or (len(k) > 3 and any(w.startswith(k) for w in words)))


def match_line(labels: list[str], item: WardrobeItem | None) -> int | None:
    """Index of the receipt line that names this piece (keywords of its subcategory), or None."""
    if item is None or not labels:
        return None
    sub = (item.subcategory or "").lower()
    keywords = LINE_KEYWORDS.get(sub, tuple(w for w in re.split(r"[\s-]+", sub) if len(w) > 2))
    scores = [_score(set(re.split(r"[^a-z0-9-]+", _plain(label))), keywords) for label in labels]
    best = max(range(len(labels)), key=scores.__getitem__)
    return best if scores[best] > 0 else None


def hint_for(item: WardrobeItem | None) -> dict:
    """Context sent to M8 so it can pick the right line on a multi-article receipt."""
    hint: dict = {"languages": ["fr", "ar", "en"], "default_currency": "TND"}
    if item is not None:
        hint |= {"category": item.category.value, "subcategory": item.subcategory,
                 "colors": [c.name for c in item.colors], "brand": item.brand}
    return hint


def finalize(doc: DocumentResponse, item: WardrobeItem | None) -> DocumentResponse:
    """Pick the receipt line of this piece (if M8 did not) and take its price when there is no total."""
    if doc.kind == DocumentKind.auto:
        raise ValueError("an extraction must report the detected kind")
    if doc.lines and doc.selected_line is None:
        doc.selected_line = match_line([line.label for line in doc.lines], item)
    if doc.selected_line is not None and not 0 <= doc.selected_line < len(doc.lines):
        doc.selected_line = None
    if doc.selected_line is not None and doc.fields.price is None:
        doc.fields.price = doc.lines[doc.selected_line].price
    if doc.fields.price is not None and doc.fields.currency is None:
        doc.fields.currency = "TND"
    return doc


def _receipt_url(user_id: str, item_id: str, image: str) -> str:
    data = images.read_image_bytes(image)
    img = images.open_image(data)                        # validates, EXIF, <= 1024 px
    return storage.save_image(user_id, item_id, "receipt", images.encode(img, "JPEG"), "jpg")


def prepare_changes(item: WardrobeItem, update: ItemUpdate) -> dict:
    """Validated changes to apply; stores (or deletes) the receipt image when the user asked for it."""
    changes = update.changes()
    if item.status == ItemStatus.pending and "status" in changes:
        raise InvalidUpdateError("a pending item is accepted with POST /items/{id}/confirm, not with status")
    if "category" in changes and changes["category"] is None:
        raise InvalidUpdateError("category cannot be empty")
    if "receipt_image" in changes:
        if changes["receipt_image"] is None:
            storage.delete_image(item.user_id, item.item_id, "receipt")
        elif not str(changes["receipt_image"]).startswith(storage.MEDIA_URL):   # a new upload
            changes["receipt_image"] = _receipt_url(item.user_id, item.item_id, changes["receipt_image"])
    if "purchase_date" in changes and changes["purchase_date"] is not None and "purchase_year" not in changes:
        changes["purchase_year"] = changes["purchase_date"].year
    for key in ("season", "care", "composition", "colors"):
        if key in changes and changes[key] is None:
            changes[key] = []                                            # list fields are never null
    return changes


def to_db(changes: dict) -> dict:
    """Plain values for SQLAlchemy (JSON columns get dicts, enums their value, dates stay dates)."""
    out = {}
    for key, value in changes.items():
        if isinstance(value, list):
            out[key] = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
        elif isinstance(value, StrEnum):
            out[key] = value.value
        else:
            out[key] = value
    return out
