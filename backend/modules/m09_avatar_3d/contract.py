"""M9 input / output. Agree them on day 1, change only through a PR reviewed by the owner.

A piece = phone photo(s) + its sheet (type, size, fit, grammage, length). Rendering = body (sex, height,
weight) + pieces -> GLB of a faceless avatar wearing them (MPFB body + CC0 MakeHuman garments, built in
Blender).
"""

from pydantic import BaseModel, Field

SIZES = ("XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "4XL")
FITS = ("slim", "regular", "relaxed", "oversize")
LENGTHS = ("mini", "midi", "long")
SLEEVES = ("short", "long")


class PieceSheet(BaseModel):
    """What the user tells about a piece (the photo gives the rest)."""

    # t-shirt, jersey, polo shirt, shirt, long-sleeve top, sweater, hoodie, pants, jeans, cargo pants, shorts,
    # skirt, dress, jacket, blazer, shoes
    type: str = "t-shirt"
    size: str | None = Field(default="M", description="XXS..4XL; None = template's own fit")
    fit: str = "regular"  # slim / regular / relaxed / oversize
    gsm: float | None = None  # grammage g/m2; None = typical for the type
    length: str | None = None  # skirts: mini / midi / long
    sleeves: str | None = None  # tops: short / long; None = the type's own sleeves
    color: str | None = None  # "#rrggbb" when there is no photo
    name: str | None = None


class Body(BaseModel):
    sex: str = "female"  # female / male
    height_cm: float = Field(default=165, ge=120, le=230)
    weight_kg: float = Field(default=60, ge=30, le=200)


class RenderPayload(Body):
    piece_ids: list[str] = []


class RenderRequest(BaseModel):
    user_id: str | None = None
    payload: RenderPayload = RenderPayload()


class RenderResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
