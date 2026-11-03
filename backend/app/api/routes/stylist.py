"""Talk to the stylist and get an outfit from the signed-in wardrobe."""

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.clothing_item import ClothingItem

router = APIRouter(prefix="/stylist", tags=["stylist"])


def build_embedder():
    from recommender.fashionclip import FashionCLIP

    return FashionCLIP()


class PieceRead(BaseModel):
    id: str
    name: str
    slot: str
    score: float


class StylistRead(BaseModel):
    reply: str
    request: dict
    shops: list[dict]
    memory: dict
    recommendations: list[PieceRead]
    outfit: list[PieceRead]


def _owned(db: DbSession, user_id: UUID) -> list[ClothingItem]:
    from sqlalchemy import select

    return list(db.scalars(select(ClothingItem).where(ClothingItem.user_id == user_id)))


@router.post("/chat", response_model=StylistRead)
async def chat(
    db: DbSession,
    user: CurrentUser,
    message: str = Form(""),
    weather: str = Form(""),
    season: str = Form(""),
    occasion: str = Form(""),
    size: str = Form(""),
    budget: float | None = Form(None),
    image: UploadFile | None = File(None),
) -> StylistRead:
    from app.services.stylist_bridge import advise

    settings = get_settings()
    photo = await image.read() if image is not None else None
    try:
        turn = advise(
            user_id=str(user.id),
            items=_owned(db, user.id),
            message=message,
            weather=weather,
            season=season,
            occasion=occasion,
            size=size,
            budget=budget,
            image=photo or None,
            data_dir=settings.stylist_data,
            llm_base_url=settings.llm_base_url,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            embedder=build_embedder(),
        )
    except (RuntimeError, ImportError, OSError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The stylist model is not ready. Install torch and transformers, then retry.",
        ) from exc
    recommendations = [_piece(item) for item in turn.recommendations]
    outfit = [_piece(item) for item in (turn.outfit.pieces if turn.outfit else [])]
    return StylistRead(
        reply=turn.reply,
        request=turn.request,
        shops=turn.shops,
        memory=turn.memory,
        recommendations=recommendations,
        outfit=outfit,
    )


def _piece(item) -> PieceRead:
    return PieceRead(id=item.piece.id, name=item.piece.name, slot=item.piece.slot, score=round(item.score, 4))
