"""BodyProfile → avatar parameters.

MVP: three presets plus a height-based vertical scale applied to the whole
scene group (avatar and garments together, so they stay aligned). Later the
`parameters` dict drives shape keys on the parametric base avatar.
"""

from app.models.body_profile import BodyProfile
from app.schemas.avatar import AvatarRead, AvatarScale
from app.schemas.common import AvatarPreset

BASE_AVATAR_URL = "/models/avatar/base_avatar.glb"
BASE_HEIGHT_CM = 178.0

PRESET_SCALES: dict[str, tuple[float, float]] = {
    "slim": (0.9, 0.92),
    "average": (1.0, 1.0),
    "broad": (1.12, 1.08),
}

REFERENCE_MEASUREMENTS = {
    "chest_cm": 96.0,
    "waist_cm": 82.0,
    "hips_cm": 98.0,
    "shoulder_width_cm": 44.0,
    "arm_length_cm": 60.0,
    "leg_length_cm": 82.0,
}


def build_avatar(profile: BodyProfile | None) -> AvatarRead:
    preset: AvatarPreset = "average"
    if profile and profile.avatar_preset in PRESET_SCALES:
        preset = profile.avatar_preset  # type: ignore[assignment]
    width, depth = PRESET_SCALES[preset]

    height = profile.height_cm if profile and profile.height_cm else BASE_HEIGHT_CM
    height_scale = max(0.85, min(1.15, height / BASE_HEIGHT_CM))

    parameters = {"height_ratio": round(height / BASE_HEIGHT_CM, 3)}
    for field, reference in REFERENCE_MEASUREMENTS.items():
        value = getattr(profile, field, None) if profile else None
        parameters[field.removesuffix("_cm") + "_ratio"] = round((value or reference) / reference, 3)

    return AvatarRead(
        base_model_url=BASE_AVATAR_URL,
        preset=preset,
        scale=AvatarScale(x=width, y=round(height_scale, 3), z=depth),
        parameters=parameters,
    )
