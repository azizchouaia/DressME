"""BO5 input / output. Built on shared schemas; change via PR."""

from typing import Literal

from pydantic import BaseModel, Field


class Body(BaseModel):
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None


class SmartBuyInput(BaseModel):
    user_id: str
    probe_image: str                         # s3://... or local path / demo id
    price_tnd: float | None = None
    shop_brand: str | None = None            # for size advice (M18)
    body: Body | None = None
    need_for_occasion: bool | None = None    # answer to the 'close call' question
    ai_confidence: float | None = None       # photo recognition confidence (0-1), from M1 / vision


class Neighbour(BaseModel):
    item_id: str
    label: str
    similarity: float


class ScoreBreakdown(BaseModel):
    new_outfits: float
    gap_fill: float
    novelty: float
    price_value: float


class SizeAdvice(BaseModel):
    brand: str
    size: str
    note: str


class BuyLink(BaseModel):
    shop: str
    item: str
    price_tnd: float
    url: str
    promo_code: str | None = None
    subcategory: str | None = None
    colour: str | None = None


class SmartBuyOutput(BaseModel):
    verdict: Literal["buy", "think", "skip"]
    score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    category: str
    is_duplicate: bool
    similar_items: list[Neighbour] = []
    new_outfits: int = 0
    pairs_with: list[str] = []
    fills_gap: str | None = None
    cost_per_outfit_tnd: float | None = None
    reasons: list[str] = []
    explanation: str = ""
    size_advice: SizeAdvice | None = None
    buy_links: list[BuyLink] = []
    # --- decision upgrades
    decision_mode: Literal["rules", "learned"] = "rules"
    probabilities: dict[str, float] | None = None      # learned mode
    contributions: dict[str, float] = {}               # XAI: + pushes toward BUY, - away
    what_if: list[str] = []                            # counterfactuals
    uncertain: bool = False
    question: str | None = None
    question_key: str | None = None                    # e.g. 'need_for_occasion'
    predicted_wears: int | None = None                 # per year
    cost_per_wear_tnd: float | None = None
    threshold_offset: int = 0                          # personal strictness (bandit)
    # --- personal goals (M5, mocked)
    goals: list[str] = []
    goal_fit: float | None = None                      # -1 breaks the goals .. +1 helps them
    fills_goal: str | None = None
