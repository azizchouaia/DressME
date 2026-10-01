from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class OutfitFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    shirt_id: UUID | None = None
    pants_id: UUID | None = None
    jacket_id: UUID | None = None
    shoes_id: UUID | None = None
    accessory_ids: list[UUID] = Field(default_factory=list)


class OutfitCreate(OutfitFields):
    pass


class OutfitUpdate(BaseModel):
    """Partial update: send only the slots that change, e.g. just `shirt_id`."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    shirt_id: UUID | None = None
    pants_id: UUID | None = None
    jacket_id: UUID | None = None
    shoes_id: UUID | None = None
    accessory_ids: list[UUID] | None = None


class OutfitRead(OutfitFields, ORMModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
