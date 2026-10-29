"""M5 input / output. Used by BO1 BO2 BO4 BO6 BO8 BO9: change only through a PR reviewed by the owner (BO4).

service.py implements every endpoint. mock.py only keeps the week-1 envelope functions (profile, gaps)
used by the BO8 orchestrator; their shapes are at the end of this file.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import get_config

Reaction = Literal["reject", "ignored", "accept", "like", "heart", "worn"]
FeedbackSource = Literal["swipe", "worn", "chat", "onboarding"]


def _check_occasion(value: str) -> str:
    value = value.strip().lower()
    allowed = get_config().context.all_occasions()
    if value not in allowed:
        raise ValueError(f"unknown occasion {value!r}, expected one of {allowed}")
    return value


class Context(BaseModel):
    """The situation of a recommendation. Weather comes from the client for now (mock provider)."""

    temp_c: float = Field(default=20.0, ge=-30, le=55)
    rain: bool = False
    occasion: str = "casual"
    weekend: bool | None = Field(default=None, description="default: from `date` (today when absent)")
    date: dt.date | None = None

    _occasion = field_validator("occasion")(_check_occasion)

    def is_weekend(self) -> bool:
        if self.weekend is not None:
            return self.weekend
        return (self.date or dt.date.today()).weekday() >= 5


class StyleShare(BaseModel):
    style: str
    family: str
    share: float


# --- profile (built from the swipes only: no questions, no wardrobe analysis) -----------------------


class ProfileResponse(BaseModel):
    user_id: str
    onboarded: bool = Field(description="true once every card of the onboarding swipe batch is answered")
    answers: dict = Field(description="explicit wishes from POST /preferences: want_more, want_less")
    style_mix: dict[str, float] = Field(description="style mix of the liked cards (empty before any like)")
    families: dict[str, float]
    top_families: list[str]
    top_styles: list[StyleShare]
    taste_vector: list[float] | None = Field(description="512-d, L2-normalised, M1 FashionCLIP space")
    n_feedback: int
    styles_version: str
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


# --- cards (onboarding swipes + daily loop) ---------------------------------------------------------


class Card(BaseModel):
    log_id: str = Field(description="send it back with the feedback")
    kind: Literal["outfit", "look"]
    outfit_id: str | None = None
    look_id: str | None = None
    title: str | None = None
    item_ids: list[str] = []
    images: list[str] = Field(default=[], description="to preload: item cutouts / look image")
    context: Context
    rank: int
    score: float = Field(description="rocchio: cosine(card, taste); bandit: sampled / mean model score")
    explore: bool = Field(default=False, description="discovery card, picked away from the taste (rocchio)")
    top_styles: list[StyleShare]


class CardsResponse(BaseModel):
    user_id: str
    cards: list[Card]
    n_candidates: int
    candidates_source: str = Field(description="request / m02 / m02_mock / reference_looks")
    styles_version: str
    elapsed_ms: float


class CandidateIn(BaseModel):
    outfit_id: str | None = None
    item_ids: list[str] = Field(min_length=1)


class ChooseRequest(BaseModel):
    user_id: str = Field(min_length=1)
    context: Context = Context()
    candidates: list[CandidateIn] | None = Field(
        default=None, max_length=200, description="M2 outfits; absent -> M5 asks M2 (or its mock)"
    )
    k: int | None = Field(default=None, ge=1, le=50, description="default: bandit.batch_size (10)")
    explore: bool = Field(default=True, description="false = rank by the mean model (no exploration)")


class FeedbackEvent(BaseModel):
    log_id: str | None = Field(default=None, description="from a card: the shown features are reused")
    outfit_id: str | None = None
    look_id: str | None = None
    item_ids: list[str] | None = Field(default=None, description="an outfit never shown (e.g. worn, M3)")
    reaction: Reaction
    source: FeedbackSource = "swipe"
    context: Context | None = Field(default=None, description="needed when there is no shown card")

    @model_validator(mode="after")
    def _target(self):
        if not (self.log_id or self.outfit_id or self.look_id or self.item_ids):
            raise ValueError("give log_id, outfit_id, look_id or item_ids")
        return self


class FeedbackRequest(BaseModel):
    user_id: str = Field(min_length=1)
    events: list[FeedbackEvent] = Field(min_length=1, max_length=200)


class FeedbackResult(BaseModel):
    index: int
    log_id: str | None
    status: Literal["applied", "duplicate", "skipped"] = Field(
        description="duplicate: this card already has a reward; skipped: features of an older style list"
    )
    reward: float | None = None
    weight: float | None = None


class FeedbackResponse(BaseModel):
    user_id: str
    applied: int
    results: list[FeedbackResult]
    n_feedback: int


class ExplainRule(BaseModel):
    feature: str
    label: str = Field(description="readable sentence, for 'why this outfit' and BO8")
    weight: float
    uncertainty: float | None = Field(default=None, description="bandit: posterior std of the weight")


class ExplainResponse(BaseModel):
    user_id: str
    n_feedback: int
    positive: list[ExplainRule]
    negative: list[ExplainRule]
    card: list[ExplainRule] | None = Field(default=None, description="why the card log_id was shown")


class PreferencesRequest(BaseModel):
    """'More classic, less streetwear': explicit wishes after the first swipes (coach agent, settings)."""

    user_id: str = Field(min_length=1)
    more: list[str] = Field(default=[], max_length=5, description="style ids to see more of")
    less: list[str] = Field(default=[], max_length=5, description="style ids to see less of")

    @model_validator(mode="after")
    def _some_change(self):
        if not (self.more or self.less):
            raise ValueError("give at least one style in more or less")
        if set(self.more) & set(self.less):
            raise ValueError("a style cannot be in both more and less")
        return self


class RecomputeRequest(BaseModel):
    user_id: str | None = Field(default=None, description="also recompute this user's item mixes now")


class RecomputeResponse(BaseModel):
    styles_version: str
    n_styles: int
    dim: int
    dropped: int = Field(description="stored item mixes of an older style list, recomputed lazily")
    recomputed: int


# --- style coach agent (POST /agent/chat) -----------------------------------------------------------


class AgentChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=64, description="absent -> a new conversation")


class AgentStep(BaseModel):
    tool: str
    args: dict
    result: str = Field(description="what the tool answered to the LLM (shortened)")


class AgentChatResponse(BaseModel):
    user_id: str
    thread_id: str
    reply: str
    steps: list[AgentStep] = Field(description="tool calls of this turn, in order")
    cards: list[Card] = Field(default=[], description="outfits proposed in this turn")
    profile_changed: bool
    model: str
    elapsed_ms: float


class StylesResponse(BaseModel):
    version: str
    families: dict[str, dict]
    styles: list[dict]
    dim: int


# --- errors raised by service.py (mapped to HTTP codes by router.py) --------------------------------


class ProfileNotFoundError(LookupError):
    """404: no profile / card for this user."""


class InvalidAnswerError(ValueError):
    """422: unknown style id or log id."""


# --- week-1 envelope (kept for the BO8 orchestrator tool) -------------------------------------------


class ProfileRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ProfileEnvelope(BaseModel):
    result: dict = {}
    mocked: bool = True


class GapsRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class GapsResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
