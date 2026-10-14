"""M2 input / output. Agree them on day 1, change only through a PR reviewed by the owner.

Every endpoint keeps the team envelope {user_id, payload} -> {result, mocked}; the payload is typed below.
Items come from M1 (Garment + its FashionCLIP embedding). Until M1 is live, M2 falls back to its demo
wardrobes
(user_id "demo_f" / "demo_m"), or the caller passes the items inline in `payload.items`.
"""

import datetime as dt

from pydantic import BaseModel, Field

from shared.schemas import Garment, Outfit, OutfitContext, Weather


class WardrobeItem(Garment):
    """A Garment as M1 serves it, plus its item vector: 1024 floats =
    [FashionCLIP image embedding (512) | FashionCLIP text embedding of its description (512)],
    model patrickjohncyh/fashion-clip, each half L2-normalised (input of the pretrained OutfitTransformer)."""

    status: str = "available"  # available / laundry / lent (from M3)
    embedding: list[float] | None = None


class WearEntry(BaseModel):
    """One day of the wear log (from M3)."""

    date: dt.date
    item_ids: list[str]


class Context(BaseModel):
    occasion: str = "casual"  # work / casual / event
    mood: str | None = None  # comfy / bold / classy
    city: str = "Tunis"
    date: dt.date | None = None  # default today; tomorrow = "outfit the night before"
    weather: Weather | None = None  # skip the weather API when given


class Options(BaseModel):
    n: int = Field(default=3, ge=1, le=10)
    rotation_window_days: int = 7  # pieces worn in this window are penalised (0 = off)
    forgotten_after_days: int = 60  # dormant pieces get a bonus (0 = off), max one per outfit
    allow_outerwear: bool | None = None  # None = decided by the weather
    exclude_item_ids: list[str] = []
    style_vector: list[float] | None = None  # taste vector from M5 (same space as the item embeddings)


class BasePayload(BaseModel):
    context: Context = Context()
    options: Options = Options()
    items: list[WardrobeItem] | None = None  # inline wardrobe; None = load it for user_id
    wear_log: list[WearEntry] = []


class RecommendPayload(BasePayload):
    pass


class RemixPayload(BasePayload):
    base_item_ids: list[str] = []  # the outfit of the day; the remix shares at most one piece with it


class CompletePayload(BasePayload):
    pinned_item_ids: list[str] = []


class SwapPayload(BasePayload):
    item_ids: list[str]  # the current outfit
    slot: str  # category to replace: top / bottom / dress / outerwear / shoes


class ScorePayload(BasePayload):
    outfits: list[list[str]]  # outfits to score, as lists of item ids


class ScoreBreakdown(BaseModel):
    compatibility: float
    weather_fit: float
    occasion_fit: float
    mood_fit: float
    style_match: float
    novelty: float
    rotation_penalty: float
    forgotten_bonus: float


class RankedOutfit(Outfit):
    score: float = 0.0
    score_breakdown: ScoreBreakdown | None = None
    slots: dict[str, str] = {}  # slot -> item_id
    reasons: list[str] = []  # facts behind the score, for M8 / the "why this outfit" screen
    forgotten_item_id: str | None = None


class OutfitsResult(BaseModel):
    outfits: list[RankedOutfit] = []
    items: dict[str, dict] = {}  # item_id -> name, image, colours, attributes... of every piece used
    context: OutfitContext | None = None
    weather_source: str | None = None  # open-meteo / request / fallback


class RecommendRequest(BaseModel):
    user_id: str | None = None
    payload: RecommendPayload = RecommendPayload()


class RemixRequest(BaseModel):
    user_id: str | None = None
    payload: RemixPayload = RemixPayload()


class CompleteRequest(BaseModel):
    user_id: str | None = None
    payload: CompletePayload = CompletePayload()


class SwapRequest(BaseModel):
    user_id: str | None = None
    payload: SwapPayload


class ScoreRequest(BaseModel):
    user_id: str | None = None
    payload: ScorePayload


class OutfitsResponse(BaseModel):
    result: OutfitsResult = OutfitsResult()
    mocked: bool = True


# Kept for backwards compatibility with the week-0 skeleton.
RecommendResponse = OutfitsResponse
