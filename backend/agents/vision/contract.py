"""Input/output of the VisionAgent. Built from shared schemas."""

from typing import Literal

from pydantic import BaseModel

from shared.schemas import Garment

class VisionInput(BaseModel):
    user_id: str
    image: str                       # s3://... raw photo
    mode: Literal["add_to_wardrobe", "smartbuy_probe", "inspiration_photo"] = "add_to_wardrobe"


class VisionOutput(BaseModel):
    garment: Garment
    embedding: list[float]
    needs_confirmation: bool         # True when confidence < threshold
