from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ClothingItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "clothing_items"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), index=True, default="other")
    subcategory: Mapped[str | None] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(40))
    secondary_color: Mapped[str | None] = mapped_column(String(40))
    pattern: Mapped[str | None] = mapped_column(String(40))
    brand: Mapped[str | None] = mapped_column(String(80))
    size: Mapped[str | None] = mapped_column(String(20))
    material: Mapped[str | None] = mapped_column(String(60))
    sleeve_type: Mapped[str | None] = mapped_column(String(40))

    image_url: Mapped[str | None] = mapped_column(String(500))
    image_key: Mapped[str | None] = mapped_column(String(300))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    thumbnail_key: Mapped[str | None] = mapped_column(String(300))
    glb_url: Mapped[str | None] = mapped_column(String(500))

    # uploaded | analyzing | analyzed | processing_3d | ready | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")

    # Latest AI suggestion, kept separate from the user-confirmed fields above.
    ai_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Future input for GarmentFitService, e.g. {"chest_cm": 108, "length_cm": 70}.
    garment_measurements: Mapped[dict[str, float] | None] = mapped_column(JSON)
