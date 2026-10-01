from typing import Literal

from pydantic import BaseModel, ConfigDict

ClothingCategory = Literal[
    "t-shirt", "shirt", "pants", "jeans", "jacket", "dress", "shoes", "accessory", "other"
]
ClothingStatus = Literal["uploaded", "analyzing", "analyzed", "processing_3d", "ready", "failed"]
AvatarPreset = Literal["slim", "average", "broad"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
