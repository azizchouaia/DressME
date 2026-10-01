from pydantic import BaseModel, Field

from app.schemas.common import AvatarPreset, ORMModel


class BodyMeasurements(BaseModel):
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=300)
    chest_cm: float | None = Field(default=None, ge=50, le=200)
    waist_cm: float | None = Field(default=None, ge=40, le=200)
    hips_cm: float | None = Field(default=None, ge=50, le=200)
    shoulder_width_cm: float | None = Field(default=None, ge=25, le=80)
    arm_length_cm: float | None = Field(default=None, ge=40, le=100)
    leg_length_cm: float | None = Field(default=None, ge=50, le=130)


class BodyProfileUpdate(BodyMeasurements):
    avatar_preset: AvatarPreset = "average"


class BodyProfileRead(BodyMeasurements, ORMModel):
    avatar_preset: AvatarPreset
    source: str
