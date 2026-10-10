"""DATA CONTRACT — change only through a PR reviewed by M6."""

import datetime as dt

from pydantic import BaseModel, Field


class Weather(BaseModel):
    temp_c: float
    condition: str


class OutfitContext(BaseModel):
    occasion: str
    date: dt.date | None = None
    weather: Weather | None = None


class OutfitScores(BaseModel):
    compatibility: float = Field(ge=0, le=1)
    style_match: float | None = Field(default=None, ge=0, le=1)
    weather_fit: float | None = Field(default=None, ge=0, le=1)


class Outfit(BaseModel):
    outfit_id: str
    user_id: str
    items: list[str]
    context: OutfitContext | None = None
    scores: OutfitScores | None = None
    explanation: str | None = None
    source: str = "stylist_agent"
    tryon_render: str | None = None
