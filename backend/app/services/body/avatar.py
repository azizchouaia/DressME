"""BodyProfile → avatar parameters.

The wearable body is always the shared human mesh. Height scales the whole
figure. Chest, waist, hips, shoulders, and limb length are ratios the viewer
applies to that mesh and to the wardrobe clothes authored on it, so a jacket
follows the same dimensions as the body.

A photo reconstruction, when present, replaces the figure you see. Clothes
stay on the standard body, because the photo mesh has no shared fit.
"""

from app.models.body_profile import BodyProfile
from app.schemas.avatar import AvatarRead, AvatarScale
from app.schemas.common import AvatarPreset

BASE_AVATAR_URL = "/models/avatar/base_avatar.glb"
BASE_HEIGHT_CM = 178.0

# Girth multiplies chest, waist, hips, and shoulders. Depth is the front-to-back scale.
PRESET_BUILD: dict[str, tuple[float, float]] = {
    "slim": (0.92, 0.94),
    "average": (1.0, 1.0),
    "broad": (1.1, 1.06),
}

REFERENCE_MEASUREMENTS = {
    "chest_cm": 96.0,
    "waist_cm": 82.0,
    "hips_cm": 98.0,
    "shoulder_width_cm": 44.0,
    "arm_length_cm": 60.0,
    "leg_length_cm": 82.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ratio(profile: BodyProfile | None, field: str, reference: float, low: float, high: float, extra: float = 1.0) -> float:
    value = getattr(profile, field, None) if profile else None
    return round(_clamp(((value or reference) / reference) * extra, low, high), 3)


def build_avatar(profile: BodyProfile | None) -> AvatarRead:
    preset: AvatarPreset = "average"
    if profile and profile.avatar_preset in PRESET_BUILD:
        preset = profile.avatar_preset  # type: ignore[assignment]
    girth, depth = PRESET_BUILD[preset]

    height = profile.height_cm if profile and profile.height_cm else BASE_HEIGHT_CM
    height_scale = _clamp(height / BASE_HEIGHT_CM, 0.85, 1.18)

    parameters = {
        "height_ratio": round(height_scale, 3),
        "chest_ratio": _ratio(profile, "chest_cm", REFERENCE_MEASUREMENTS["chest_cm"], 0.8, 1.35, girth),
        "waist_ratio": _ratio(profile, "waist_cm", REFERENCE_MEASUREMENTS["waist_cm"], 0.75, 1.4, girth),
        "hips_ratio": _ratio(profile, "hips_cm", REFERENCE_MEASUREMENTS["hips_cm"], 0.8, 1.35, girth),
        "shoulder_width_ratio": _ratio(
            profile, "shoulder_width_cm", REFERENCE_MEASUREMENTS["shoulder_width_cm"], 0.85, 1.3, girth
        ),
        "arm_length_ratio": _ratio(profile, "arm_length_cm", REFERENCE_MEASUREMENTS["arm_length_cm"], 0.85, 1.2),
        "leg_length_ratio": _ratio(profile, "leg_length_cm", REFERENCE_MEASUREMENTS["leg_length_cm"], 0.85, 1.2),
        "depth_ratio": round(depth, 3),
    }
    photo = profile.avatar_glb_url if profile else None
    return AvatarRead(
        base_model_url=photo or BASE_AVATAR_URL,
        preset=preset,
        scale=AvatarScale(x=1.0, y=round(height_scale, 3), z=1.0),
        from_photo=bool(photo),
        photo_model_url=photo,
        parameters=parameters,
    )
