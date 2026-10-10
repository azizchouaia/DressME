"""Input/output of the TryOnAgent. Built from shared schemas."""

from typing import Literal

from pydantic import BaseModel

from shared.schemas import BodyMeasurements

class TryOnInput(BaseModel):
    user_id: str
    body: BodyMeasurements
    items: list[str]
    mode: Literal["3d", "2d_fallback"] = "3d"


class TryOnOutput(BaseModel):
    avatar: str                      # s3://.../avatar.glb
    render: str                      # s3://.../outfit.glb
    preview_png: str | None = None
    latency_ms: int | None = None
