from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ClothingCategory, ClothingStatus, ORMModel


class ClothingFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: ClothingCategory = "other"
    subcategory: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=40)
    secondary_color: str | None = Field(default=None, max_length=40)
    pattern: str | None = Field(default=None, max_length=40)
    brand: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=20)
    material: str | None = Field(default=None, max_length=60)
    sleeve_type: str | None = Field(default=None, max_length=40)


class ClothingCreate(ClothingFields):
    glb_url: str | None = Field(default=None, max_length=500)


class ClothingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: ClothingCategory | None = None
    subcategory: str | None = None
    color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    brand: str | None = None
    size: str | None = None
    material: str | None = None
    sleeve_type: str | None = None
    glb_url: str | None = None
    status: ClothingStatus | None = None


class ClothingAnalysisRead(BaseModel):
    category: ClothingCategory | None = None
    subcategory: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    sleeve_type: str | None = None
    brand: str | None = None
    confidence: float = 0.0
    analyzer: str


class ClothingItemRead(ClothingFields, ORMModel):
    id: UUID
    user_id: UUID
    image_url: str | None
    thumbnail_url: str | None
    glb_url: str | None
    status: ClothingStatus
    ai_analysis: ClothingAnalysisRead | None = None
    garment_measurements: dict[str, float] | None = None
    created_at: datetime
    updated_at: datetime


class Garment3DStatus(BaseModel):
    item_id: UUID
    status: ClothingStatus
    glb_url: str | None
    message: str
