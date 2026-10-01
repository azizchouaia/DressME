from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.body_profile import BodyProfile
from app.schemas.body import BodyProfileRead, BodyProfileUpdate

router = APIRouter(prefix="/body-profile", tags=["body"])


def get_or_create_profile(db: DbSession, user: CurrentUser) -> BodyProfile:
    if user.body_profile is None:
        user.body_profile = BodyProfile(user_id=user.id, avatar_preset="average", source="manual")
        db.flush()
    return user.body_profile


@router.get("", response_model=BodyProfileRead)
def read_body_profile(db: DbSession, user: CurrentUser) -> BodyProfile:
    profile = get_or_create_profile(db, user)
    db.commit()
    return profile


@router.put("", response_model=BodyProfileRead)
def update_body_profile(payload: BodyProfileUpdate, db: DbSession, user: CurrentUser) -> BodyProfile:
    profile = get_or_create_profile(db, user)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    profile.source = "manual"
    db.commit()
    return profile
