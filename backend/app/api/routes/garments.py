from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.api.routes.wardrobe import get_owned_item
from app.schemas.clothing import Garment3DStatus
from app.services.garments.processing import get_garment_processor

router = APIRouter(prefix="/garments", tags=["garments"])


@router.post(
    "/{item_id}/process-3d", response_model=Garment3DStatus, status_code=status.HTTP_202_ACCEPTED
)
def process_3d(item_id: UUID, db: DbSession, user: CurrentUser) -> Garment3DStatus:
    item = get_owned_item(db, user, item_id)
    result = get_garment_processor().submit(item)
    item.status = result.status
    if result.glb_url:
        item.glb_url = result.glb_url
    if result.category:
        item.category = result.category
    db.commit()
    db.refresh(item)
    return Garment3DStatus(
        item_id=item.id,
        status=item.status,
        glb_url=item.glb_url,
        category=item.category,
        message=result.message,
    )


@router.get("/{item_id}/3d-status", response_model=Garment3DStatus)
def read_3d_status(item_id: UUID, db: DbSession, user: CurrentUser) -> Garment3DStatus:
    item = get_owned_item(db, user, item_id)
    message = "3D model ready." if item.glb_url else "No 3D model for this item yet."
    return Garment3DStatus(item_id=item.id, status=item.status, glb_url=item.glb_url, message=message)
