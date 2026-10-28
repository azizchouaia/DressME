"""Mock of M1 (USE_MOCKS=true, default). Same functions and signatures as service.py.

Demo user `usr_demo` owns 13 pieces (incl. a near-duplicate navy shirt). State is kept in memory, so
classify (add_to_wardrobe) and delete really change the wardrobe until the process restarts.
Embeddings are deterministic: items of the same "family" are ~0.78 similar, the two navy shirts ~0.96.
classify() cannot see the garment: it picks a plausible template from the photo shape and hash, but the
colours are really computed (LAB K-means on the centre of the photo).
"""

import hashlib
import io
import uuid
import zlib
from datetime import UTC, date, datetime

import numpy as np

from shared.schemas import Color, GarmentCategory

from . import details, storage
from .config import get_config
from .contract import (
    EMBEDDING_DIM,
    ClassifyMode,
    ClassifyRequest,
    ClassifyResponse,
    DeleteResponse,
    DocumentKind,
    DocumentRequest,
    DocumentResponse,
    DuplicatesRequest,
    DuplicatesResponse,
    ItemNotFoundError,
    ItemsRequest,
    ItemsResponse,
    ItemStatus,
    ItemUpdate,
    OnDuplicate,
    SimilarItem,
    SimilarRequest,
    SimilarResponse,
    WardrobeItem,
)
from .pipeline import images
from .pipeline.dedup import group_pairs, pairs_above

DEMO_USER = "usr_demo"
ASSETS = "/m01/ui/assets"
FAMILY_WEIGHT = 0.78          # share of the "family" direction in an item embedding

_C = GarmentCategory
# (item_id, file, category, subcategory, colors[(name, hex, share)], pattern, material, season,
#  formality, local_tag, confidence, wear_count, last_worn, price_tnd, family)
_DEMO = [
    ("itm_demo_shirt_navy", "shirt-navy", _C.top, "linen shirt",
     [("navy", "#1F2A44", 0.88), ("white", "#F2F0EA", 0.07)], "solid", "linen",
     ["spring", "summer"], 0.55, None, 0.94, 14, date(2026, 10, 9), 89.0, "shirt"),
    ("itm_demo_shirt_navy_2", "shirt-navy-2", _C.top, "shirt",
     [("navy", "#24314F", 0.91)], "solid", "cotton",
     ["spring", "summer", "autumn"], 0.5, None, 0.88, 3, date(2026, 8, 21), 65.0, "shirt"),
    ("itm_demo_chino_beige", "chino-beige", _C.bottom, "chinos",
     [("beige", "#D6C1A1", 0.93)], "solid", "cotton",
     ["spring", "summer", "autumn"], 0.5, None, 0.91, 22, date(2026, 10, 12), 120.0, "bottom"),
    ("itm_demo_jeans_blue", "jeans-blue", _C.bottom, "jeans",
     [("denim", "#4A6A8F", 0.86), ("tan", "#B07A45", 0.04)], "solid", "denim",
     ["spring", "autumn", "winter"], 0.3, None, 0.96, 41, date(2026, 10, 14), 149.0, "bottom"),
    ("itm_demo_sneakers_white", "sneakers-white", _C.shoes, "sneakers",
     [("white", "#F4F2EE", 0.78), ("light grey", "#C9C7C2", 0.17)], "solid", "leather",
     ["spring", "summer", "autumn"], 0.2, None, 0.97, 58, date(2026, 10, 14), 259.0, "shoes"),
    ("itm_demo_jacket_leather", "jacket-leather-black", _C.outerwear, "leather jacket",
     [("black", "#1E1C1A", 0.9), ("silver", "#BFC1C2", 0.04)], "solid", "leather",
     ["autumn", "winter", "spring"], 0.45, None, 0.93, 17, date(2026, 3, 2), 450.0, "leather"),
    ("itm_demo_bag_brown", "bag-leather-brown", _C.accessory, "bag",
     [("brown", "#6F4A2D", 0.84), ("gold", "#C4A35A", 0.05)], "solid", "leather",
     ["spring", "summer", "autumn", "winter"], 0.6, None, 0.9, 30, date(2026, 10, 10), 320.0, "leather"),
    ("itm_demo_dress_red", "dress-summer-red", _C.dress, "summer dress",
     [("red", "#B3261E", 0.92)], "solid", "cotton",
     ["summer"], 0.35, None, 0.89, 6, date(2026, 8, 30), 135.0, "dress"),
    ("itm_demo_jebba_white", "jebba-white", _C.traditional, "jebba",
     [("white", "#F5F1E8", 0.82), ("gold", "#C4A882", 0.08)], "embroidered", "silk",
     ["spring", "summer"], 0.85, "jebba", 0.81, 2, date(2026, 4, 1), 680.0, "dress"),
    ("itm_demo_sweatshirt_grey", "sweatshirt-grey", _C.top, "sweatshirt",
     [("grey", "#8E8E8C", 0.94)], "solid", "cotton",
     ["autumn", "winter"], 0.15, None, 0.92, 25, date(2026, 10, 3), 79.0, "shirt"),
    ("itm_demo_belt_brown", "belt-brown", _C.accessory, "belt",
     [("brown", "#5E3E26", 0.8), ("gold", "#C4A35A", 0.12)], "solid", "leather",
     ["spring", "summer", "autumn", "winter"], 0.6, None, 0.86, 35, date(2026, 10, 12), 55.0, "leather"),
    ("itm_demo_sunglasses", "sunglasses-black", _C.accessory, "sunglasses",
     [("black", "#171512", 0.74), ("dark brown", "#3E2A1E", 0.2)], "solid", "synthetic",
     ["spring", "summer"], 0.4, None, 0.95, 44, date(2026, 10, 11), 210.0, "glasses"),
    ("itm_demo_loafers", "loafers-camel", _C.shoes, "loafers",
     [("tan", "#A0703F", 0.87)], "solid", "suede",
     ["spring", "summer", "autumn"], 0.65, None, 0.9, 12, date(2026, 9, 27), 289.0, "shoes"),
]

# classify(): what a "recognised" upload can become, picked deterministically from the image hash
_TEMPLATES = [
    (_C.top, "t-shirt", "cotton", "solid", ["spring", "summer"], 0.2, "shirt"),
    (_C.top, "shirt", "cotton", "striped", ["spring", "summer", "autumn"], 0.5, "shirt"),
    (_C.bottom, "trousers", "wool", "solid", ["autumn", "winter"], 0.7, "bottom"),
    (_C.outerwear, "blazer", "wool", "solid", ["autumn", "winter", "spring"], 0.8, "leather"),
    (_C.dress, "dress", "cotton", "floral", ["spring", "summer"], 0.45, "dress"),
    (_C.shoes, "boots", "leather", "solid", ["autumn", "winter"], 0.5, "shoes"),
    (_C.accessory, "scarf", "wool", "checked", ["autumn", "winter"], 0.4, "glasses"),
    (_C.traditional, "kachabia", "wool", "striped", ["winter"], 0.6, "dress"),
]

_DB: dict[str, dict[str, tuple[WardrobeItem, np.ndarray]]] = {}
_HANGING = {_C.top, _C.bottom, _C.dress, _C.outerwear, _C.traditional}


def _pick_template(key: str, img) -> tuple:
    """Portrait photo -> something that hangs, landscape -> shoes / accessory, else anything."""
    pool = _TEMPLATES
    if img is not None:
        w, h = img.size
        if h > 1.15 * w:
            pool = [t for t in _TEMPLATES if t[0] in _HANGING]
        elif w > 1.15 * h:
            pool = [t for t in _TEMPLATES if t[0] not in _HANGING]
    return pool[int(key[:8], 16) % len(pool)]


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _rand(seed_text: str) -> np.ndarray:
    rng = np.random.default_rng(zlib.crc32(seed_text.encode()))
    return _unit(rng.standard_normal(EMBEDDING_DIM))


def _embedding(seed_text: str, family: str) -> np.ndarray:
    return _unit(np.sqrt(FAMILY_WEIGHT) * _rand(f"family:{family}")
                 + np.sqrt(1 - FAMILY_WEIGHT) * _rand(f"item:{seed_text}"))


def _seed() -> dict[str, tuple[WardrobeItem, np.ndarray]]:
    wardrobe: dict[str, tuple[WardrobeItem, np.ndarray]] = {}
    for n, (item_id, file, cat, sub, colors, pattern, material, season, formality, local_tag, conf,
            wears, last_worn, price, family) in enumerate(_DEMO):
        url = f"{ASSETS}/{file}.svg"
        item = WardrobeItem(
            item_id=item_id, user_id=DEMO_USER, image_raw=url, image_cutout=url, category=cat,
            subcategory=sub, colors=[Color(name=c, hex=h, share=s) for c, h, s in colors],
            pattern=pattern, material=material, season=season, formality=formality, local_tag=local_tag,
            embedding_id=item_id, confidence=conf, wear_count=wears, last_worn=last_worn,
            created_at=datetime(2026, 1, 5 + n, 10, 0, tzinfo=UTC), price_tnd=price,
        )
        wardrobe[item_id] = (item, _embedding(item_id, family))
    # the second navy shirt is a near-copy of the first one (similarity ~0.93)
    first = wardrobe["itm_demo_shirt_navy"][1]
    wardrobe["itm_demo_shirt_navy_2"] = (
        wardrobe["itm_demo_shirt_navy_2"][0],
        _unit(np.sqrt(0.93) * first + np.sqrt(0.07) * _rand("item:navy-2-noise")),
    )
    return wardrobe


def _wardrobe(user_id: str) -> dict[str, tuple[WardrobeItem, np.ndarray]]:
    if user_id not in _DB:
        _DB[user_id] = _seed() if user_id == DEMO_USER else {}
    return _DB[user_id]


def _reset() -> None:
    """Tests only: back to the seeded demo wardrobe."""
    _DB.clear()


def _neighbours(user_id: str, vector: np.ndarray, k: int, threshold: float, exclude: str | None = None):
    scored = [
        SimilarItem(item_id=i, similarity=round(float(np.clip(vector @ v, -1, 1)), 4))
        for i, (item, v) in _wardrobe(user_id).items()
        if i != exclude and item.status == "active"
    ]
    scored.sort(key=lambda n: n.similarity, reverse=True)
    return [n for n in scored[:k] if n.similarity >= threshold]


def _image_key(image: str) -> tuple[bytes | None, str]:
    """(decoded bytes or None for URLs, stable hash of the image)."""
    if image.startswith(("http://", "https://")):
        return None, hashlib.sha1(image.encode()).hexdigest()
    data = images.read_image_bytes(image)
    return data, hashlib.sha1(data).hexdigest()


def _colors_from(img, fallback: list[Color]) -> list[Color]:
    """Real LAB K-means on the centre of the photo (no background removal in the mock)."""
    try:
        from .pipeline.colors import dominant_colors

        w, h = img.size
        centre = img.convert("RGBA").crop((w // 5, h // 5, w - w // 5, h - h // 5))
        return dominant_colors(centre, get_config().palette) or fallback
    except ImportError:          # scikit-learn not installed: the mock still works
        return fallback


async def classify(req: ClassifyRequest) -> ClassifyResponse:
    cfg = get_config()
    data, key = _image_key(req.image)
    img = images.open_image(data) if data is not None else None
    cat, sub, material, pattern, season, formality, family = _pick_template(key, img)
    confidence = round(0.70 + (int(key[8:12], 16) % 30) / 100, 2)          # 0.70 .. 0.99
    colors = _colors_from(img, [Color(name="beige", hex="#D8C3A5", share=0.9)]) if img else [
        Color(name="beige", hex="#D8C3A5", share=0.9)]
    embedding = _embedding(key, family)

    stored = req.mode == ClassifyMode.add_to_wardrobe
    item_id = f"itm_{uuid.uuid4().hex[:12]}"
    if stored and img is not None:
        buf = io.BytesIO()
        img.convert("RGBA").save(buf, format="PNG")
        image_raw = storage.save_image(req.user_id, item_id, "raw", buf.getvalue(), "png")
    else:
        image_raw = req.image if data is None else "inline"

    garment = WardrobeItem(
        item_id=item_id, user_id=req.user_id, image_raw=image_raw,
        image_cutout=None, category=cat, subcategory=sub,   # the mock does not remove backgrounds
        colors=colors, pattern=pattern, material=material, season=season, formality=formality,
        local_tag=sub if cat == _C.traditional else None, embedding_id=item_id if stored else None,
        confidence=confidence, created_at=datetime.now(UTC), price_tnd=req.price_tnd,
    )
    duplicates = _neighbours(req.user_id, embedding, 5, cfg.thresholds.duplicate)
    pending = stored and bool(duplicates) and req.on_duplicate == OnDuplicate.ask
    if stored:
        garment.status = ItemStatus.pending if pending else ItemStatus.active
        _wardrobe(req.user_id)[item_id] = (garment, embedding)
    return ClassifyResponse(
        garment=garment, embedding=embedding.tolist(),
        needs_confirmation=confidence < cfg.thresholds.confidence,
        duplicates=duplicates, stored=stored and not pending, pending=pending, mocked=True,
    )


async def similar(req: SimilarRequest) -> SimilarResponse:
    threshold = get_config().thresholds.similar if req.threshold is None else req.threshold
    wardrobe = _wardrobe(req.user_id)
    if req.item_id is not None:
        if req.item_id not in wardrobe:
            raise ItemNotFoundError(req.item_id)
        vector = wardrobe[req.item_id][1]
    else:
        _, key = _image_key(req.image)
        family = _TEMPLATES[int(key[:8], 16) % len(_TEMPLATES)][-1]
        vector = _embedding(key, family)
    return SimilarResponse(
        neighbours=_neighbours(req.user_id, vector, req.k, threshold, exclude=req.item_id), mocked=True
    )


async def duplicates(req: DuplicatesRequest) -> DuplicatesResponse:
    threshold = get_config().thresholds.duplicate if req.threshold is None else req.threshold
    active = [(i, v) for i, (item, v) in _wardrobe(req.user_id).items() if item.status == "active"]
    ids = [i for i, _ in active]
    vectors = np.array([v for _, v in active]) if active else np.zeros((0, EMBEDDING_DIM))
    return DuplicatesResponse(groups=group_pairs(pairs_above(ids, vectors, threshold)), mocked=True)


async def items(req: ItemsRequest) -> ItemsResponse:
    found = []
    for item, _ in _wardrobe(req.user_id).values():
        if req.category and item.category != req.category:
            continue
        if req.status and item.status != req.status:
            continue
        if not req.status and item.status == ItemStatus.pending:
            continue
        if req.season and req.season.lower() not in item.season:
            continue
        if req.color and req.color.lower() not in {c.name for c in item.colors}:
            continue
        found.append(item)
    return ItemsResponse(items=found, total=len(found), mocked=True)


async def get_item(user_id: str, item_id: str) -> WardrobeItem:
    wardrobe = _wardrobe(user_id)
    if item_id not in wardrobe:
        raise ItemNotFoundError(item_id)
    return wardrobe[item_id][0]


async def confirm_item(user_id: str, item_id: str) -> WardrobeItem:
    wardrobe = _wardrobe(user_id)
    if item_id not in wardrobe or wardrobe[item_id][0].status != ItemStatus.pending:
        raise ItemNotFoundError(f"{item_id} (no pending item with this id)")
    wardrobe[item_id][0].status = ItemStatus.active
    return wardrobe[item_id][0]


async def update_item(user_id: str, item_id: str, update: ItemUpdate) -> WardrobeItem:
    wardrobe = _wardrobe(user_id)
    if item_id not in wardrobe:
        raise ItemNotFoundError(item_id)
    item, embedding = wardrobe[item_id]
    changes = details.prepare_changes(item, update)
    updated = WardrobeItem.model_validate(item.model_dump(exclude={"shelf"}) | changes)
    wardrobe[item_id] = (updated, embedding)
    return updated


# what M8 would read on typical Tunisian receipts / labels (the mock cannot read the photo)
_DOCUMENTS = {
    DocumentKind.receipt: {
        "kind": "receipt",
        "fields": {"currency": "TND", "purchase_date": "2026-09-14",
                   "store": "Zara · Tunisia Mall, Les Berges du Lac", "brand": "Zara"},
        "lines": [{"label": "CHEMISE LIN MARINE  M", "price": 89.0},
                  {"label": "CHINO COTON BEIGE 40", "price": 119.9},
                  {"label": "CEINTURE CUIR MARRON", "price": 55.0}],
        "confidence": {"purchase_date": 0.97, "store": 0.9, "brand": 0.88, "price": 0.95},
    },
    DocumentKind.price_tag: {
        "kind": "price_tag",
        "fields": {"price": 89.0, "currency": "TND", "brand": "Zara", "size": "M", "size_system": "letter",
                   "reference": "4387/512/401"},
        "confidence": {"price": 0.98, "brand": 0.93, "size": 0.96, "reference": 0.9},
    },
    DocumentKind.care_label: {
        "kind": "care_label",
        "fields": {"size": "M", "size_system": "letter",
                   "composition": [{"material": "lin", "percent": 100}],
                   "care": ["Lavage en machine à 30 °C", "Ne pas utiliser de sèche-linge",
                            "Repassage à température moyenne", "Nettoyage à sec autorisé"]},
        "confidence": {"composition": 0.97, "care": 0.85, "size": 0.9},
    },
}


async def extract_document(req: DocumentRequest) -> DocumentResponse:
    item = await get_item(req.user_id, req.item_id) if req.item_id else None
    data, _ = _image_key(req.image)
    if data is not None:
        images.open_image(data)                                     # same validation as the real service
    kind = DocumentKind.receipt if req.kind == DocumentKind.auto else req.kind
    doc = DocumentResponse.model_validate(_DOCUMENTS[kind] | {"mocked": True})
    return details.finalize(doc, item)


async def delete_item(user_id: str, item_id: str) -> DeleteResponse:
    wardrobe = _wardrobe(user_id)
    if wardrobe.pop(item_id, None) is None:
        raise ItemNotFoundError(item_id)
    storage.delete_images(user_id, item_id)
    return DeleteResponse(item_id=item_id, deleted=True, mocked=True)
