from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.body_profile import BodyProfile
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.db.seed import ensure_demo_user
from app.services.clothing.samples import seed_sample_wardrobe

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = create_user(db, email, payload.password, payload.display_name.strip())
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.post("/demo", response_model=TokenResponse)
def demo_login(db: DbSession) -> TokenResponse:
    """Sign in to the shared demo account. Disabled when SEED_DEMO_USER=false."""
    settings = get_settings()
    if not settings.seed_demo_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo account is disabled.")
    ensure_demo_user(db)
    user = db.scalar(select(User).where(User.email == settings.demo_email))
    assert user is not None
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


def create_user(db: DbSession, email: str, password: str, display_name: str) -> User:
    user = User(email=email, display_name=display_name, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    db.add(BodyProfile(user_id=user.id, avatar_preset="average", source="manual"))
    seed_sample_wardrobe(db, user.id)
    return user
