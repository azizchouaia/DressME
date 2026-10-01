from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.avatar import AvatarRead
from app.services.body.avatar import build_avatar

router = APIRouter(prefix="/avatar", tags=["avatar"])


@router.get("", response_model=AvatarRead)
def read_avatar(user: CurrentUser) -> AvatarRead:
    return build_avatar(user.body_profile)


@router.post("/generate", response_model=AvatarRead)
def generate_avatar(user: CurrentUser) -> AvatarRead:
    """Recompute avatar parameters from the body profile. In the MVP this is
    deterministic; later it may trigger a Blender job for a custom mesh."""
    return build_avatar(user.body_profile)
