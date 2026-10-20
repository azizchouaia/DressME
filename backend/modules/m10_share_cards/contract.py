"""Input/output of the ShareAgent (shared module M10 · Share / export cards). Built from shared schemas.

Used by BO4 (style card), BO5 (boutique-tagged shares), BO6 (local brands), BO7 (all sharing ideas)
and BO9 (try-on look). Every caller sends the same `ShareCardInput`; only `kind` and the content change.
"""

from typing import Literal

from pydantic import BaseModel, Field

from shared.schemas import GarmentCategory

CardKind = Literal[
    "outfit",  # outfit of the day / recommendation (BO7 S2)
    "board",  # builder board export (BO7 S3)
    "tryon",  # 3D avatar look (BO7 S4, BO9)
    "recap",  # monthly wardrobe recap (BO7 S8)
    "giveaway",  # give-away post (BO7 S10)
    "challenge",  # community challenge entry (M15)
    "style_timeline",  # style evolution (BO7 B4, BO4)
    "trip",  # trip lookbook (BO7 B5)
    "poll",  # "should I buy this?" poll (BO7 S7)
]

CardFormat = Literal["story", "square", "post"]  # 1080x1920 · 1080x1080 · 1080x1350


class CardItem(BaseModel):
    item_id: str
    category: GarmentCategory
    label: str | None = None
    image: str | None = None  # cutout from M1: s3://, http(s)://, data: URI or local path
    color_hex: str | None = None  # dominant colour from M1, used for the palette and placeholders
    brand: str | None = None  # local brand tag from M7 (BO6 / BO7 B3)


class PipelineStep(BaseModel):
    """One step of Input → Code → Output, shown in the demo and the report."""

    stage: Literal["input", "code", "output"]
    method: str  # "data", "if/else", "ML", "DL", "LLM · PE", "LLM · RAG", "stats"
    name: str
    detail: str


class CardStat(BaseModel):
    label: str
    value: str


class ShareCardInput(BaseModel):
    user_id: str
    kind: CardKind = "outfit"
    items: list[CardItem] = Field(default_factory=list, max_length=8)
    title: str | None = None
    subtitle: str | None = None  # e.g. "Tuesday · 24°C · work"
    caption: str | None = None  # if empty, a caption is generated
    stats: list[CardStat] = Field(default_factory=list, max_length=6)
    format: CardFormat = "story"
    source_id: str | None = None  # outfit_id, challenge entry id, ... (for attribution)
    watermark: bool = True
    language: str = "en"  # caption language: en | fr | tn (Tunisian in Latin letters)
    qr: bool = False  # QR code of the referral link on the card (printed flyers, screens, stories)


class ShareCardOutput(BaseModel):
    card_id: str
    short_code: str
    image_url: str  # API path or s3:// URL of the PNG
    share_url: str  # public link with referral code
    width: int
    height: int
    caption: str
    alt_text: str
    background_hex: str
    caption_source: Literal["user", "llm", "template"] = "template"
    channel_links: dict[str, str] = {}  # whatsapp / instagram / facebook / x / copy, each tagged with ?ch=
    pipeline: list[PipelineStep] = []
    retrieved: list[dict] = []  # RAG documents used for the caption
    prompt: str | None = None  # prompt sent to the LLM (prompt engineering, for transparency)


# ---- Generic shapes of the team template (POST /m10/card) ----
class CardRequest(BaseModel):
    """`payload` = a `ShareCardInput` (see above)."""

    user_id: str | None = None
    payload: dict = {}


class CardResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
