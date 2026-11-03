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
    # A photo mesh is a raw preview. The wearable body stays base_model_url.
    from_photo: bool = False
    photo_model_url: str | None = None
    # Ratios the phone viewer applies to the human body and to clothes
    # authored on it: girth bands, limb length, and overall height.
    parameters: dict[str, float]
