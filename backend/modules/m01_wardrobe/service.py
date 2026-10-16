"""Real implementation of M1 (USE_MOCKS=false). Same functions and signatures as mock.py.

classify: decode -> rembg cutout -> FashionCLIP zero-shot + embedding -> LAB K-means colours
          -> duplicates (pgvector) -> store (add_to_wardrobe only).
Models are loaded lazily on the first call; CPU-heavy steps run in a worker thread.
"""

import asyncio
import base64
import uuid
from dataclasses import dataclass

import numpy as np

from shared.schemas import Color

from . import details, m08_client, storage, store
from .config import get_config
from .contract import (
    ClassifyMode,
    ClassifyRequest,
    ClassifyResponse,
    DeleteResponse,
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
    SimilarRequest,
    SimilarResponse,
    WardrobeItem,
)
from .pipeline import images
from .pipeline.classifier import Attributes, describe
from .pipeline.dedup import group_pairs


@dataclass
class Analysis:
    raw: bytes
    raw_ext: str
    cutout_png: bytes
    attributes: Attributes | None
    colors: list[Color]
    embedding: np.ndarray


def new_item_id() -> str:
    return f"itm_{uuid.uuid4().hex[:12]}"


def _analyse(data: bytes, full: bool = True) -> Analysis:
    """Synchronous, CPU-heavy. `full=False` only computes the embedding (for /similar)."""
    from .pipeline.clip import get_clip
    from .pipeline.colors import dominant_colors
    from .pipeline.cutout import on_white, remove_background

    cfg = get_config()
    img = images.open_image(data)
    cutout = remove_background(img)
    clip = get_clip()
    emb = clip.embed_image(on_white(cutout))
    if not full:
        return Analysis(b"", "png", b"", None, [], emb)
    raw_ext = "png" if images.has_alpha(img) else "jpg"
    return Analysis(
        raw=images.encode(img, "PNG" if raw_ext == "png" else "JPEG"),
        raw_ext=raw_ext,
        cutout_png=images.encode(cutout, "PNG"),
        attributes=describe(clip, emb, cfg),
        colors=dominant_colors(cutout, cfg.palette),
        embedding=emb,
    )


async def classify(req: ClassifyRequest) -> ClassifyResponse:
    cfg = get_config()
    data = await asyncio.to_thread(images.read_image_bytes, req.image)
    a = await asyncio.to_thread(_analyse, data)
    attrs = a.attributes
    stored = req.mode == ClassifyMode.add_to_wardrobe
    item_id = new_item_id()

    if stored:
        image_raw = storage.save_image(req.user_id, item_id, "raw", a.raw, a.raw_ext)
        image_cutout = storage.save_image(req.user_id, item_id, "cutout", a.cutout_png, "png")
    else:  # probes are not persisted
        image_raw = req.image if req.image.startswith(("http://", "https://")) else "inline"
        image_cutout = None

    garment = WardrobeItem(
        item_id=item_id,
        user_id=req.user_id,
        image_raw=image_raw,
        image_cutout=image_cutout,
        category=attrs.category,
        subcategory=attrs.subcategory,
        colors=a.colors,
        pattern=attrs.pattern,
        material=attrs.material,
        season=attrs.season,
        formality=attrs.formality,
        local_tag=attrs.local_tag,
        embedding_id=item_id if stored else None,
        confidence=attrs.confidence,
        price_tnd=req.price_tnd,
    )

    await store.ensure_schema()
    duplicates = await store.nearest(req.user_id, a.embedding, k=5, min_similarity=cfg.thresholds.duplicate)
    # possible duplicate: keep it pending until the user accepts (confirm_item) or cancels (delete_item)
    pending = stored and bool(duplicates) and req.on_duplicate == OnDuplicate.ask
    if stored:
        garment.status = ItemStatus.pending if pending else ItemStatus.active
        garment = await store.add_item(garment, a.embedding)

    return ClassifyResponse(
        garment=garment,
        embedding=[float(x) for x in a.embedding],
        needs_confirmation=attrs.confidence < cfg.thresholds.confidence,
        duplicates=duplicates,
        stored=stored and not pending,
        pending=pending,
    )


async def similar(req: SimilarRequest) -> SimilarResponse:
    threshold = get_config().thresholds.similar if req.threshold is None else req.threshold
    await store.ensure_schema()
    if req.item_id is not None:
        vector = await store.get_embedding(req.user_id, req.item_id)
        if vector is None:
            raise ItemNotFoundError(req.item_id)
    else:
        data = await asyncio.to_thread(images.read_image_bytes, req.image)
        vector = (await asyncio.to_thread(_analyse, data, False)).embedding
    neighbours = await store.nearest(req.user_id, vector, req.k, threshold, exclude_id=req.item_id)
    return SimilarResponse(neighbours=neighbours)


async def duplicates(req: DuplicatesRequest) -> DuplicatesResponse:
    threshold = get_config().thresholds.duplicate if req.threshold is None else req.threshold
    await store.ensure_schema()
    pairs = await store.duplicate_pairs(req.user_id, threshold)
    return DuplicatesResponse(groups=group_pairs(pairs))


async def items(req: ItemsRequest) -> ItemsResponse:
    await store.ensure_schema()
    found = await store.list_items(req)
    return ItemsResponse(items=found, total=len(found))


async def get_item(user_id: str, item_id: str) -> WardrobeItem:
    await store.ensure_schema()
    item = await store.get_item(user_id, item_id)
    if item is None:
        raise ItemNotFoundError(item_id)
    return item


async def confirm_item(user_id: str, item_id: str) -> WardrobeItem:
    """Accepts a pending item (possible duplicate): it joins the wardrobe."""
    await store.ensure_schema()
    item = await store.set_status(user_id, item_id, ItemStatus.pending.value, ItemStatus.active.value)
    if item is None:
        raise ItemNotFoundError(f"{item_id} (no pending item with this id)")
    return item


async def update_item(user_id: str, item_id: str, update: ItemUpdate) -> WardrobeItem:
    """The form: user's details (size, price, brand...) and corrections of the AI."""
    item = await get_item(user_id, item_id)
    changes = await asyncio.to_thread(details.prepare_changes, item, update)
    updated = await store.update_item(user_id, item_id, details.to_db(changes))
    if updated is None:
        raise ItemNotFoundError(item_id)
    return updated


async def extract_document(req: DocumentRequest) -> DocumentResponse:
    """Receipt / price tag / care label -> proposed fields, through M8. Nothing is saved."""
    item = await get_item(req.user_id, req.item_id) if req.item_id else None
    data = await asyncio.to_thread(images.read_image_bytes, req.image)
    img = await asyncio.to_thread(images.open_image, data)
    data_url = "data:image/jpeg;base64," + base64.b64encode(images.encode(img, "JPEG")).decode()
    doc = await m08_client.extract(req.user_id, data_url, req.kind, details.hint_for(item))
    return details.finalize(doc, item)


async def delete_item(user_id: str, item_id: str) -> DeleteResponse:
    await store.ensure_schema()
    if not await store.delete_item(user_id, item_id):
        raise ItemNotFoundError(item_id)
    storage.delete_images(user_id, item_id)
    return DeleteResponse(item_id=item_id, deleted=True)
