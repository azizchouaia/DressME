from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.clothing_item import ClothingItem
from app.schemas.clothing import (
    ClothingAnalysisRead,
    ClothingCreate,
    ClothingItemRead,
    ClothingUpdate,
)
from app.schemas.common import ClothingCategory
from app.services.ai import get_clothing_analyzer
from app.services.clothing.images import InvalidImageError, store_clothing_image
from app.services.storage import get_storage

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


def get_owned_item(db: DbSession, user: CurrentUser, item_id: UUID) -> ClothingItem:
    item = db.get(ClothingItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clothing item not found.")
    return item


@router.get("", response_model=list[ClothingItemRead])
def list_wardrobe(
    db: DbSession,
    user: CurrentUser,
    category: Annotated[ClothingCategory | None, Query()] = None,
) -> list[ClothingItem]:
    query = select(ClothingItem).where(ClothingItem.user_id == user.id)
    if category:
        query = query.where(ClothingItem.category == category)
    return list(db.scalars(query.order_by(ClothingItem.created_at.desc())))


@router.post("", response_model=ClothingItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: ClothingCreate, db: DbSession, user: CurrentUser) -> ClothingItem:
    item = ClothingItem(
        user_id=user.id, status="ready" if payload.glb_url else "analyzed", **payload.model_dump()
    )
    db.add(item)
    db.commit()
    return item


@router.post("/upload", response_model=ClothingItemRead, status_code=status.HTTP_201_CREATED)
async def upload_item(
    db: DbSession,
    user: CurrentUser,
    image: Annotated[UploadFile, File()],
    name: Annotated[str, Form(max_length=120)] = "New item",
) -> ClothingItem:
    """Create a draft item from a photo. Metadata is confirmed later via PUT."""
    data = await image.read()
    try:
        stored = store_clothing_image(get_storage(), user.id, data)
    except InvalidImageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    item = ClothingItem(
        user_id=user.id,
        name=name,
        category="other",
        status="uploaded",
        image_url=stored.image_url,
        image_key=stored.image_key,
        thumbnail_url=stored.thumbnail_url,
        thumbnail_key=stored.thumbnail_key,
    )
    db.add(item)
    db.commit()
    return item


@router.get("/{item_id}", response_model=ClothingItemRead)
def read_item(item_id: UUID, db: DbSession, user: CurrentUser) -> ClothingItem:
    return get_owned_item(db, user, item_id)


@router.put("/{item_id}", response_model=ClothingItemRead)
def update_item(
    item_id: UUID, payload: ClothingUpdate, db: DbSession, user: CurrentUser
) -> ClothingItem:
    item = get_owned_item(db, user, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    if payload.status is None and item.status in ("uploaded", "analyzing"):
        item.status = "analyzed"
    db.commit()
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, db: DbSession, user: CurrentUser) -> None:
    item = get_owned_item(db, user, item_id)
    storage = get_storage()
    for key in (item.image_key, item.thumbnail_key):
        if key:
            storage.delete(key)
    db.delete(item)
    db.commit()


@router.post("/{item_id}/analyze", response_model=ClothingAnalysisRead)
async def analyze_item(item_id: UUID, db: DbSession, user: CurrentUser) -> ClothingAnalysisRead:
    """Run the configured analyzer. Results are suggestions; the item's
    confirmed fields are not modified until the user saves them."""
    item = get_owned_item(db, user, item_id)
    if not item.image_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This item has no photo to analyze.")

    previous_status = item.status
    item.status = "analyzing"
    db.commit()
    analyzer = get_clothing_analyzer()
    try:
        analysis = await analyzer.analyze(get_storage().read(item.image_key))
    except Exception as exc:
        item.status = previous_status
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Clothing analysis failed.") from exc

    result = ClothingAnalysisRead(**analysis.__dict__)
    item.ai_analysis = result.model_dump()
    item.status = "analyzed" if previous_status in ("uploaded", "analyzing") else previous_status
    db.commit()
    return result
