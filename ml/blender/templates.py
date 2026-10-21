"""Garment type (as M1 / the Kaggle labels name it) -> 3D template (CC0 MakeHuman clothes) + defaults.

asset        MPFB clothes folder
kind         layer: shoes < bottom < dress < top < outerwear
gsm          typical grammage (g/m2) when the user does not give one
part         keep only a piece of a multi-part asset: "largest" island (the jacket of a suit, the shirt of a
             shirt + jeans outfit) or "above_belt"
             or "above_knee" (shorts cut from straight trousers)
scale_length False = size changes only the width (skirts, shorts, dresses keep their own length)
"""

from __future__ import annotations

T = {
    # tops
    "t-shirt": {"asset": "toigo_basic_tucked_t-shirt", "kind": "top", "gsm": 160},
    "top": {"asset": "toigo_basic_tucked_t-shirt", "kind": "top", "gsm": 150},
    "blouse": {"asset": "toigo_basic_tucked_t-shirt", "kind": "top", "gsm": 110},
    "polo shirt": {"asset": "namuhekam_male_polo_shirt", "kind": "top", "gsm": 210},
    # untucked shirts / tees: the shirt is the largest piece of a shirt + jeans outfit
    "jersey": {"asset": "male_casualsuit06", "kind": "top", "gsm": 140, "part": "largest"},
    "short-sleeve shirt": {"asset": "male_casualsuit06", "kind": "top", "gsm": 130, "part": "largest"},
    "shirt": {"asset": "male_casualsuit03", "kind": "top", "gsm": 130, "part": "largest"},
    "long-sleeve top": {"asset": "male_casualsuit02", "kind": "top", "gsm": 200, "part": "largest"},
    "sweater": {"asset": "toigo_fisherman_sweater", "kind": "top", "gsm": 320},
    "hoodie": {"asset": "toigo_fisherman_sweater", "kind": "top", "gsm": 330},
    # bottoms
    "pants": {"asset": "toigo_wool_pants", "kind": "bottom", "gsm": 300},
    "jeans": {"asset": "toigo_wool_pants", "kind": "bottom", "gsm": 380},
    "cargo pants": {"asset": "cortu_cargo_pants", "kind": "bottom", "gsm": 320},
    "shorts": {"asset": "toigo_wool_pants", "kind": "bottom", "gsm": 280, "scale_length": False, "part": "above_knee"},
    "skirt_mini": {"asset": "frankyaye_mini_skirt_01", "kind": "bottom", "gsm": 220, "scale_length": False},
    "skirt_midi": {"asset": "toigo_tiered_skirt", "kind": "bottom", "gsm": 150, "scale_length": False},
    "skirt_long": {"asset": "toigo_long_full_skirt", "kind": "bottom", "gsm": 140, "scale_length": False},
    # one-piece
    "dress": {"asset": "toigo_shift_dress", "kind": "dress", "gsm": 160, "scale_length": False},
    # outerwear (the jacket of a suit)
    "jacket": {"asset": {"male": "toigo_male_suit_tie_and_jacket", "female": "toigo_female_suit"},
               "kind": "outerwear", "gsm": 350, "part": "largest"},
    "blazer": {"asset": {"male": "toigo_male_suit_tie_and_jacket", "female": "toigo_female_suit"},
               "kind": "outerwear", "gsm": 300, "part": "largest"},
    # shoes
    "shoes": {"asset": "shoes02", "kind": "shoes", "gsm": 0},
}
ALIASES = {"longsleeve": "long-sleeve top", "long sleeve": "long-sleeve top", "polo": "polo shirt",
           "outwear": "jacket", "coat": "jacket", "trousers": "pants", "undershirt": "t-shirt", "tee": "t-shirt",
           "sweatshirt": "hoodie", "football shirt": "jersey", "sports shirt": "jersey", "joggers": "pants",
           "jogging": "pants", "sweatpants": "pants", "trackpants": "pants"}
# the sheet's "sleeves" overrides the type's own sleeves (a short-sleeve shirt, a long-sleeve tee...)
SHORT_OF = {"shirt": "short-sleeve shirt", "long-sleeve top": "t-shirt", "sweater": "t-shirt", "hoodie": "t-shirt"}
LONG_OF = {"t-shirt": "long-sleeve top", "top": "long-sleeve top", "blouse": "shirt", "jersey": "long-sleeve top",
           "short-sleeve shirt": "shirt", "polo shirt": "long-sleeve top"}


def resolve(type_name: str, sex: str, photo_info: dict | None = None, length: str | None = None,
            sleeves: str | None = None) -> dict:
    """Template for a garment type. Skirt length: the piece's sheet ("mini" / "midi" / "long") when the user
    gave it; otherwise a guess from the photo (length / waist width), which real photos (angles, folds) make
    unreliable."""
    t = type_name.lower().strip()
    t = ALIASES.get(t, t)
    if sleeves == "short":
        t = SHORT_OF.get(t, t)
    elif sleeves == "long":
        t = LONG_OF.get(t, t)
    if t == "skirt" and length in ("mini", "midi", "long"):
        t = f"skirt_{length}"
    elif t == "skirt":
        # length / waist width in the photo: a mini is about as long as its waist is wide, a midi about twice,
        # a long skirt more (the hem width is useless: flared skirts are wide at the bottom)
        ratio = (photo_info or {}).get("length_to_waist") or 1.8
        t = "skirt_mini" if ratio < 1.35 else "skirt_long" if ratio > 2.3 else "skirt_midi"
    spec = dict(T.get(t, T["t-shirt"]))
    if isinstance(spec["asset"], dict):
        spec["asset"] = spec["asset"].get(sex, next(iter(spec["asset"].values())))
    spec["type"] = t
    return spec
