from pydantic import BaseModel

from app.schemas.common import AvatarPreset


class AvatarScale(BaseModel):
    x: float
    y: float
    z: float


class AvatarRead(BaseModel):
    base_model_url: str
    preset: AvatarPreset
    scale: AvatarScale
    # Normalized parameters the parametric avatar will consume once presets
    # are replaced with continuous shape keys.
    parameters: dict[str, float]
