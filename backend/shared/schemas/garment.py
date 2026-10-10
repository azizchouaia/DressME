"""DATA CONTRACT — change only through a PR reviewed by M6."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class GarmentCategory(str, Enum):
    top = "top"
    bottom = "bottom"
    dress = "dress"
    outerwear = "outerwear"
    shoes = "shoes"
    accessory = "accessory"
    traditional = "traditional"   # jebba, kachabia, sefsari...


class Color(BaseModel):
    name: str
    hex: str
    share: float = Field(ge=0, le=1)


class Garment(BaseModel):
    item_id: str
    user_id: str
    image_raw: str
    image_cutout: str | None = None
    category: GarmentCategory
    subcategory: str | None = None
    colors: list[Color] = []
    pattern: str | None = None
    material: str | None = None
    season: list[str] = []
    formality: float | None = Field(default=None, ge=0, le=1)
    local_tag: str | None = None
    embedding_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    wear_count: int = 0
    last_worn: date | None = None
    created_at: datetime | None = None
