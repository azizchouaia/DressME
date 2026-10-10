from pydantic import BaseModel


class BodyMeasurements(BaseModel):
    height_cm: float
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None


class User(BaseModel):
    user_id: str
    city: str = "Tunis"
    locale: str = "fr"
    body: BodyMeasurements | None = None
