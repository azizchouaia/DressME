"""Input/output of the StylistAgent. Built from shared schemas."""

from pydantic import BaseModel, Field

from shared.schemas import Outfit, OutfitContext

class StylistInput(BaseModel):
    user_id: str
    context: OutfitContext
    style_vector: list[float] | None = None
    locked_items: list[str] = []     # items the outfit must contain (builder, smart buy)
    k: int = Field(default=3, ge=1, le=10)


class StylistOutput(BaseModel):
    outfits: list[Outfit]
