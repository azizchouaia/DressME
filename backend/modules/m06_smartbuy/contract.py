"""BO5 input / output. Built on shared schemas; change via PR."""

from typing import Literal

from pydantic import BaseModel, Field


class Body(BaseModel):
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    # No tape measure? Say how pieces you own fit (M18 turns it into a size)
    fit_refs: list[dict] = Field(default_factory=list)   # [{brand, size, category: top|bottom, fit}]
    like_fit: Literal["tight", "normal", "loose", "oversized"] = "normal"
    fit_text: str | None = None              # free text: "M at Zara, tight on the shoulders" (M18 reads it)


class Answer(BaseModel):
    """The user's answer to Smart Buy's last question (same session_id, no new photo needed)."""
    question_key: str                        # from the previous output, e.g. 'need_for_occasion'
    value: bool | str


class SmartBuyInput(BaseModel):
    user_id: str
    probe_image: str | None = None           # photo (data URL / http) or demo id; None when answering
    session_id: str = "default"              # conversation id from the orchestrator: memory key
    language: Literal["en", "fr", "ar"] = "en"
    answer: Answer | None = None             # answer to the question of the last call in this session
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
    city: str | None = None
    image_url: str | None = None
    product_id: str | None = None          # M7 id: send it back with the click (/m13/click)
    search_id: str | None = None
    rank: int | None = None
    sizes: str | None = None               # sizes the shop sells
    source: str = "fictional"              # m7 (real Tunisian shop) | fictional


class NextAction(BaseModel):
    """What the orchestrator can do next (chain another agent or ask the user)."""
    action: str                              # ask_user / open_shop / show_outfits / find_cheaper / feedback...
    label: str                               # text for a button or for the orchestrator LLM
    tool: str | None = None                  # agent / module to call: smartbuy, m02, m07, m13
    args: dict = {}


class AgentInfo(BaseModel):
    name: str
    version: str


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
    sources: dict[str, str] = {}
    # --- agent identity + memory
    agent: AgentInfo | None = None
    session_id: str = "default"
    decision_id: str | None = None                     # send it back with feedback (bought / liked)
    piece: str | None = None                           # what was judged, e.g. 'White shirt'
    memory_notes: list[str] = []                       # what Smart Buy remembered for this answer
    next_actions: list[NextAction] = []                       # which module answered each step: m1 / m2 / m7 / mock
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
