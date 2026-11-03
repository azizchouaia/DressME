from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class BodyProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "body_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    chest_cm: Mapped[float | None] = mapped_column(Float)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    hips_cm: Mapped[float | None] = mapped_column(Float)
    shoulder_width_cm: Mapped[float | None] = mapped_column(Float)
    arm_length_cm: Mapped[float | None] = mapped_column(Float)
    leg_length_cm: Mapped[float | None] = mapped_column(Float)

    # slim | average | broad — replaced by continuous parameters later.
    avatar_preset: Mapped[str] = mapped_column(String(20), default="average")
    # manual | photo. A photo source means avatar_glb_url is a reconstruction
    # of the person's picture, standing in the same viewer as the template body.
    source: Mapped[str] = mapped_column(String(20), default="manual")
    avatar_glb_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="body_profile")
