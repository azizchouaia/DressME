"""M14 input / output (Stylist / boutique mode). Change only through a PR reviewed by the owner (BO6).

Who uses what: BO4 -> review (F3) · BO5 -> instore (F5) · BO6 -> dashboard (F6) · BO7 -> looks (F4) ·
BO8 -> handoff (F7). Every answer that used another module says in `sources` whether it was real or mock.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ProType = Literal["stylist", "boutique"]
Language = Literal["en", "fr", "ar"]


# ---------- F1 · professional accounts ----------
class Loyalty(BaseModel):
    """A boutique's loyalty code, set by the shop itself (its agreement with DressMe), shown on its pieces."""

    code: str = Field(pattern=r"^[A-Z0-9-]{3,24}$", description="Said at the till, e.g. MANUELLA10")
    discount_pct: int = Field(ge=1, le=70)
    until: date | None = Field(None, description="Last valid day; none = until removed")
    conditions: str | None = Field(None, max_length=120, description="e.g. from 100 TND, in the shop only")


class ProIn(BaseModel):
    type: ProType
    name: str = Field(min_length=2, max_length=80)
    city: str | None = Field(None, description="City of the pro (Tunis, Sousse...)")
    shop: str | None = Field(
        None, description="Boutique only: shop name as in the M7 catalogue (GET /m07/shops)"
    )
    specialities: list[str] = Field(
        default_factory=list, description="e.g. mariage, traditionnel, bureau, streetwear, hijab, homme"
    )
    languages: list[str] = Field(default_factory=lambda: ["fr"], description="fr / en / ar / darija")
    bio: str | None = Field(None, max_length=500)
    style_vector: list[float] | None = Field(None, description="512-d FashionCLIP centroid of the portfolio")

    @model_validator(mode="after")
    def _boutique_has_a_shop(self):
        if self.type == "boutique" and not self.shop:
            raise ValueError("a boutique account needs `shop` (a shop of the M7 catalogue)")
        return self


class Pro(ProIn):
    pro_id: str
    verified: bool = False  # set by hand by the team for the demo
    available: bool = True
    loyalty: Loyalty | None = None  # boutique accounts only (BO6 Backup 2)
    created_at: datetime


class ProUpdate(BaseModel):
    available: bool | None = None
    specialities: list[str] | None = None
    languages: list[str] | None = None
    bio: str | None = None
    loyalty: Loyalty | None = None  # boutique accounts only; remove it with DELETE /m14/pro/{id}/loyalty


# ---------- F2 · client link (consent) + brief ----------
class LinkIn(BaseModel):
    pro_id: str
    client_id: str
    message: str | None = Field(None, max_length=300, description="Shown to the client with the invitation")


class ConsentIn(BaseModel):
    client_id: str
    accept: bool


class ClientLink(BaseModel):
    link_id: str
    pro_id: str
    client_id: str
    status: Literal["invited", "active", "declined", "revoked"]
    message: str | None = None
    created_at: datetime
    answered_at: datetime | None = None


class WardrobeItem(BaseModel):
    """A piece of the client's wardrobe (M1), as the stylist sees it to build a look."""

    item_id: str
    category: str
    subcategory: str | None = None
    color: str | None = None
    wear_count: int = 0
    price_tnd: float | None = None
    image: str | None = None  # M1 photo (cut-out when available)


class Wardrobe(BaseModel):
    client_id: str
    items: list[WardrobeItem]
    sources: dict[str, str] = {}


class WardrobeSummary(BaseModel):
    n_items: int = 0
    per_category: dict[str, int] = {}
    top_colours: list[str] = []
    most_worn: list[str] = []
    never_worn: list[str] = []
    price_range_tnd: list[float] | None = None  # [min, max] of the prices the client entered


class ClientBrief(BaseModel):
    pro_id: str
    client_id: str
    archetype: str | None = None
    likes: list[str] = []
    dislikes: list[str] = []
    wardrobe: WardrobeSummary
    gaps: list[str] = []
    recent_searches: list[str] = []  # from localshop's memory (BO6)
    summary: list[str] = []  # at most 5 lines, built from the facts above
    sources: dict[str, str] = {}  # module -> real / mock


# ---------- F3 · stylist review of the style profile (BO4) ----------
class Corrections(BaseModel):
    archetype: str | None = None
    likes: list[str] = []
    dislikes: list[str] = []
    colours: list[str] = []


class ReviewIn(BaseModel):
    pro_id: str
    corrections: Corrections
    note: str | None = Field(None, max_length=500)


class Review(BaseModel):
    review_id: str
    pro_id: str
    client_id: str
    before: Corrections  # M5 profile when the stylist reviewed it
    corrections: Corrections
    changed: list[str]  # fields the stylist changed
    agreement: float = Field(ge=0, le=1)  # share of the reviewed fields the stylist kept as M5 had them
    sent_to_m5: bool
    note: str | None = None
    created_at: datetime
    sources: dict[str, str] = {}


class Agreement(BaseModel):
    n_reviews: int
    overall: float | None  # mean agreement between M5 and the stylists
    per_field: dict[str, float] = {}  # archetype / likes / dislikes / colours: share kept unchanged


# ---------- F4 · stylist sends a look to a client (BO7) ----------
class LookIn(BaseModel):
    pro_id: str
    client_id: str
    item_ids: list[str] = Field(default_factory=list, description="Pieces of the client's wardrobe (M1)")
    product_ids: list[str] = Field(default_factory=list, description="Local pieces of the M7 catalogue")
    message: str | None = Field(None, max_length=500)
    language: Language = "fr"

    @model_validator(mode="after")
    def _not_empty(self):
        if not (self.item_ids or self.product_ids):
            raise ValueError("a look needs item_ids and / or product_ids")
        return self


class LookProduct(BaseModel):
    product_id: str
    item: str
    shop: str
    price_tnd: float | None = None
    image_url: str | None = None
    image_path: str | None = None  # local copy served by M7 (GET /m07/{image_path}), for apps
    product_url: str | None = None


class Look(BaseModel):
    look_id: str
    pro_id: str
    client_id: str
    item_ids: list[str]
    products: list[LookProduct]
    total_price_tnd: float | None = None  # local pieces only
    score: float | None = None  # M2 compatibility, 0..1
    card_url: str | None = None  # M10 share card
    share_url: str | None = None
    message: str | None = None
    created_at: datetime
    sources: dict[str, str] = {}


# ---------- F2b · private conversation stylist <-> client ----------
class ChatMessageIn(BaseModel):
    sender_id: str = Field(description="The pro_id of the stylist or the client_id: nobody else can write")
    text: str = Field(min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    message_id: str
    sender_id: str
    role: Literal["stylist", "client"]
    text: str
    look_id: str | None = None  # a look sent by the stylist (F4) appears in the conversation
    created_at: datetime


class Conversation(BaseModel):
    """Private: only this stylist and this client read it; never used by the dashboard or the assistant."""

    pro_id: str
    client_id: str
    can_write: bool  # False for the stylist once the client revoked access
    messages: list[ChatMessage] = []


# ---------- F5 · in-store sales assistant (BO5) ----------
class InstoreIn(BaseModel):
    pro_id: str = Field(description="Boutique account of the seller")
    client_id: str = Field(description="Client who accepted the boutique (QR code in the shop)")
    product_id: str = Field(description="Piece of the M7 catalogue the client holds")
    language: Language = "fr"


class InstoreOut(BaseModel):
    pro_id: str
    client_id: str
    product: LookProduct
    verdict: Literal["buy", "think", "skip"]
    score: int | None = None
    reasons: list[str] = []
    explanation: str = ""
    sources: dict[str, str] = {}


# ---------- F6 · boutique demand dashboard (BO6) ----------
class Theme(BaseModel):
    theme_id: str
    label: str  # e.g. "Sandales dorées · femme"
    subcategory: str | None = None
    color: str | None = None
    gender: str | None = None
    n_searches: int
    share: float  # of the searches of the period
    median_budget_tnd: float | None = None
    top_cities: list[str] = []
    examples: list[str] = []  # most frequent requests, as typed
    zero_result_rate: float
    # no result of the asked type and colour with a good match: M7 found nothing, relaxed the colour
    # ("no gold sandals: other sandals") or matched weakly (under dashboard.unmet.low_match)
    weak_answer_rate: float


class UnmetDemand(BaseModel):
    theme_id: str
    label: str
    n_searches: int
    zero_result_rate: float
    weak_answer_rate: float
    products_in_shop: int  # in stock, same type (and colour when the theme has one)
    products_in_market: int  # the same in the whole M7 catalogue
    visual_coverage: float  # best FashionCLIP match of a shop photo with the theme, 0..1
    opportunity: float  # n_searches x (1 - coverage): what the dashboard ranks by
    hint: str  # "132 searches for “Sandals · gold · women”, 0 in your shop"


class PricePosition(BaseModel):
    subcategory: str
    label: str
    n_budgets: int  # searches that gave a budget
    demand_p25: float
    demand_p50: float
    demand_p75: float
    shop_p25: float | None = None
    shop_p50: float | None = None
    shop_p75: float | None = None
    served_share: float | None = None  # share of those budgets the shop has at least one piece for


class Trend(BaseModel):
    theme_id: str
    label: str
    last_7_days: int
    weekly_mean_before: float
    z: float
    growth: float  # last week / mean of the weeks before - 1
    rising: bool


class Funnel(BaseModel):
    impressions: int = 0  # times one of the shop's pieces was shown in results
    views: int = 0
    clicks: int = 0  # visits to the shop's website
    ctr: float = 0.0
    rank: int | None = None  # among shops, by clicks


class Dashboard(BaseModel):
    shop: str | None  # None = the whole market
    period_days: int
    since: datetime
    until: datetime
    n_searches: int
    simulated_share: float  # share of the searches that come from the simulator (said in the report)
    funnel: Funnel | None = None
    themes: list[Theme] = []
    unmet: list[UnmetDemand] = []
    prices: list[PricePosition] = []
    trends: list[Trend] = []
    not_understood: int = 0  # searches where no piece, colour or photo was understood
    hidden_groups: int = 0  # themes / rows hidden because under min_group searches
    method: dict[str, str] = {}  # how each block was computed (for the report and the UI)


class Insights(BaseModel):
    """Tips for a boutique, written by the BO6 LLM from the dashboard figures (or by rules if it is off)."""

    shop: str | None
    period_days: int
    insights: list[str] = []
    source: Literal["llm", "rules"]
    model: str | None = None  # e.g. qwen2.5:7b
    facts: list[str] = []  # the figures the tips were written from (each number of a tip comes from here)


# ---------- F7 · hand-off from the assistant to a human stylist (BO8) ----------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class EscalateIn(BaseModel):
    user_id: str
    session_id: str = "default"
    messages: list[Message] = Field(min_length=1)
    language: Language = "fr"
    ai_confidence: float | None = Field(None, ge=0, le=1, description="Assistant's confidence, if known")


class Escalation(BaseModel):
    escalate: bool
    score: float = Field(ge=0, le=1)
    reason: str | None = None  # strongest signal: asks_human, frustration, complex_occasion...
    signals: dict[str, float] = {}  # signal -> weight that fired
    by_llm: bool = False  # a signal was added by the BO6 LLM (Qwen) on a longer chat the rules missed


class HandoffIn(EscalateIn):
    city: str | None = None
    budget_tnd: float | None = None
    occasion: str | None = None
    force: bool = Field(False, description="The user tapped 'talk to a stylist': no escalation check")


class Candidate(BaseModel):
    pro_id: str
    name: str
    city: str | None = None
    score: float
    reasons: list[str] = []


class Handoff(BaseModel):
    handoff_id: str
    user_id: str
    session_id: str
    status: Literal["queued", "accepted", "declined", "closed", "not_needed", "no_stylist"]
    pro_id: str | None = None  # stylist it is queued for
    candidates: list[Candidate] = []
    escalation: Escalation
    occasion: str | None = None
    budget_tnd: float | None = None
    city: str | None = None
    summary: list[str] = []  # at most 5 lines for the stylist
    messages: list[Message] = []  # the client's conversation with the assistant
    created_at: datetime
    updated_at: datetime
    history: list[dict] = []  # status changes
    already_open: bool = False  # the client already had an open request: that one is returned


class HandoffUpdate(BaseModel):
    pro_id: str
    status: Literal["accepted", "declined", "closed"]
    note: str | None = Field(None, max_length=500)


# ---------- Backup 2 · loyalty codes, read by M7 (on the shop's pieces) and M13 (BO5, buy links) ----------
class LoyaltyCode(Loyalty):
    shop: str
    pro_id: str


# ---------- Backup 5 · local brand challenges, published through M15 (BO7) ----------
class ChallengeIn(BaseModel):
    """A boutique sponsors a community challenge: wear at least one of its pieces every day."""

    pro_id: str = Field(description="The boutique account sponsoring the challenge")
    title: str | None = Field(None, min_length=3, max_length=60, description="Default: '7 jours avec <shop>'")
    duration_days: int = Field(7, ge=3, le=31)
    min_local_pieces: int = Field(1, ge=1, le=3, description="Pieces of a local brand per day")
    no_repeat: bool = True
    language: Language = "fr"


class ChallengeRuleOut(BaseModel):
    type: str  # M15 rule types: local_brand, no_repeat...
    params: dict = {}


class LocalChallenge(BaseModel):
    challenge_id: str  # M15's id, or sim_... while M15 is simulated
    title: str
    description: str
    rules: list[ChallengeRuleOut]
    duration_days: int
    tags: list[str] = []
    sponsor: str
    participants: int = 0
    pro_id: str
    shop: str
    pieces: list[LookProduct] = []  # the shop's pieces suggested to the participants (M7)
    sources: dict[str, str] = {}  # m15 / m7 -> real | mock
    created_at: datetime
    ends_on: date | None = None  # last day: created_at + duration_days
    status: Literal["active", "ended"] = "active"  # ended: past ends_on, or ended by the shop
    ended_at: datetime | None = None  # when the shop ended it early (POST /m14/challenges/{id}/end)
