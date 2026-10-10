"""Input/output of the ProfileAgent. Built from shared schemas."""

from typing import Literal

from pydantic import BaseModel

from shared.schemas import Event

class ProfileInput(BaseModel):
    user_id: str
    events: list[Event] = []
    action: Literal["update", "get_profile", "analytics"] = "get_profile"


class StyleTraits(BaseModel):
    formality: float | None = None
    palette: list[str] = []
    avoid: list[str] = []


class WardrobeAnalytics(BaseModel):
    wear_rate: float | None = None
    never_worn: list[str] = []
    duplicates: list[list[str]] = []
    gaps: list[str] = []


class ProfileOutput(BaseModel):
    user_id: str
    style_vector: list[float] | None = None
    traits: StyleTraits = StyleTraits()
    analytics: WardrobeAnalytics | None = None
