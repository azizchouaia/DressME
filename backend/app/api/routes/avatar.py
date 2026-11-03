from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.api.routes.body import get_or_create_profile
from app.core.config import get_settings
from app.schemas.avatar import AvatarRead
from app.services.body.avatar import build_avatar
from app.services.garments.processing import TripoSRError, reconstruct_photo
from app.services.storage import get_storage

router = APIRouter(prefix="/avatar", tags=["avatar"])

# 128 marching-cubes steps keeps a phone mesh nearer the 20k–40k triangle budget
# than the garment default of 256.
_PHOTO_RESOLUTION = 128
_MAX_PHOTO_BYTES = 12 * 1024 * 1024


@router.get("", response_model=AvatarRead)
def read_avatar(user: CurrentUser) -> AvatarRead:
    return build_avatar(user.body_profile)


@router.post("/generate", response_model=AvatarRead)
def generate_avatar(user: CurrentUser) -> AvatarRead:
    """Recompute avatar parameters from the body profile."""
    return build_avatar(user.body_profile)


@router.post("/from-photo", response_model=AvatarRead)
def avatar_from_photo(
    db: DbSession,
    user: CurrentUser,
    image: UploadFile = File(...),
) -> AvatarRead:
    """Store a 3D preview of one photo. The wearable avatar stays the human body."""
    settings = get_settings()
    if settings.environment == "test" or settings.garment_processor != "triposr":
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Photo avatars need the local TripoSR service. Set GARMENT_PROCESSOR=triposr and start it.",
        )
    data = image.file.read(_MAX_PHOTO_BYTES + 1)
    if len(data) < 32:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a photo of the person, full body if you can.")
    if len(data) > _MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That photo is larger than 12 MB.")
    try:
        glb = reconstruct_photo(data, resolution=_PHOTO_RESOLUTION)
    except TripoSRError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    url = get_storage().save(f"avatars/{user.id}/body.glb", glb, "model/gltf-binary")
    profile = get_or_create_profile(db, user)
    profile.avatar_glb_url = url
    profile.source = "photo"
    db.commit()
    db.refresh(profile)
    return build_avatar(profile)


@router.delete("/from-photo", response_model=AvatarRead)
def clear_photo_avatar(db: DbSession, user: CurrentUser) -> AvatarRead:
    """Go back to the standard body. Measurements and build stay as they are."""
    profile = get_or_create_profile(db, user)
    profile.avatar_glb_url = None
    if profile.source == "photo":
        profile.source = "manual"
    db.commit()
    db.refresh(profile)
    return build_avatar(profile)
