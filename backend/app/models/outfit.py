from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


def _item_fk() -> Mapped[UUID | None]:
    return mapped_column(ForeignKey("clothing_items.id", ondelete="SET NULL"))


class Outfit(IdMixin, TimestampMixin, Base):
    __tablename__ = "outfits"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))

    shirt_id: Mapped[UUID | None] = _item_fk()
    pants_id: Mapped[UUID | None] = _item_fk()
    jacket_id: Mapped[UUID | None] = _item_fk()
    shoes_id: Mapped[UUID | None] = _item_fk()
    accessory_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
