"""Input/output of the SmartBuyAgent. Built from shared schemas."""

from typing import Literal

from pydantic import BaseModel, Field

class SmartBuyInput(BaseModel):
    user_id: str
    probe_image: str                 # s3://... photo taken in the shop
    price_tnd: float | None = None


class SmartBuyOutput(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Literal["good_buy", "duplicate", "low_value"]
    duplicates: list[str] = []
    new_outfits: int = 0
    pairs_with: list[str] = []
    reasons: list[str] = []
