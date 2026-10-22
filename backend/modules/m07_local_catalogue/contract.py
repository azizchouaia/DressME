"""Input/output of the LocalShopAgent (M7 Local catalogue). Built from shared schemas."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from shared.schemas import GarmentCategory


class Answer(BaseModel):
    """The user's answer to the agent's last question (same session_id, the request is not repeated)."""

    question_key: str | None = Field(
        None, description="question_key of the previous output (gender, max_price_tnd, query)"
    )
    value: str = Field(description="What the user said, e.g. 'femme', '150 dinars', 'une robe'")


class LocalShopInput(BaseModel):
    query: str = Field(
        "", description="Free text in FR/EN/Tunisian, e.g. 'baskets blanches à Tunis max 80 TND'"
    )
    gap: str | None = Field(None, description="Missing piece from Smart Buy / Profile, e.g. 'white shirt'")
    city: str | None = Field(None, description="Only shops in this city or its governorate (e.g. Tunis)")
    max_price_tnd: float | None = Field(None, gt=0)
    min_price_tnd: float | None = Field(None, ge=0)
    category: GarmentCategory | None = None
    subcategory: str | None = Field(None, description="e.g. sneakers, shirt, bag (see taxonomy.py)")
    color: str | None = Field(None, description="Colour code (white, navy...) or French name (blanc)")
    gender: Literal["women", "men"] | None = Field(
        None, description="Pieces for women or men; unisex pieces and pieces of unknown gender stay in"
    )
    user_id: str | None = Field(None, description="Caller's user, used to fetch their style from M5")
    style_vector: list[float] | str | None = Field(
        None,
        description="User style: id from M5 (e.g. 'vec_u042', as in the architecture) or the 512-d "
        "FashionCLIP vector itself",
    )
    image_embedding: list[float] | None = Field(
        None, description="512-d FashionCLIP embedding of a photo (Vision agent) to find similar local pieces"
    )
    include_unavailable: bool = False
    k: int = Field(10, ge=1, le=100)
    offset: int = Field(
        0, ge=0, description="Skip the first `offset` results: next page = same request with offset += k"
    )
    # --- agent memory (BO8 orchestrator): the same session_id continues the same search
    session_id: str = Field("default", description="Chat thread id from the orchestrator: memory key")
    language: Literal["en", "fr", "ar"] = Field("fr", description="Language of the question and labels")
    answer: Answer | None = Field(
        None, description="Answer to the last question of this session; the last request is reused"
    )
    next_page: bool = Field(
        False, description="Next results of the last search of this session (no need to repeat it)"
    )

    @model_validator(mode="after")
    def _something_to_search(self):
        if self.answer or self.next_page:
            return self  # the request comes from the session memory
        if not (self.query.strip() or self.gap or self.image_embedding or self.category or self.subcategory):
            raise ValueError("give a query, a gap, a category/subcategory or an image_embedding")
        return self


class ShopResult(BaseModel):
    shop: str
    area: str | None = None  # city of the shop ("; "-separated for chains), None when the shop gives none
    item: str
    price_tnd: float | None = None
    match: float = Field(ge=0, le=1)
    product_id: str
    category: str
    subcategory: str
    color: str | None = None
    gender: str | None = None  # women / men / unisex, None when unknown
    size: str | None = None
    image_url: str
    image_path: str | None = None
    product_url: str
    shop_url: str
    origin_type: str
    available: bool
    reasons: list[str] = []


class ParsedQuery(BaseModel):
    """How the request was understood: the filters actually applied (useful for explanations, M8)."""

    category: str | None = None
    subcategory: str | None = None
    color: str | None = None
    gender: str | None = None
    max_price_tnd: float | None = None
    min_price_tnd: float | None = None
    city: str | None = None
    governorate: str | None = None
    terms: list[str] = []
    prompt_en: str | None = None
    translated: str | None = None  # request after darija -> French ("sabbat ahmar" -> "chaussures rouge")
    corrected: str | None = None  # request after typo correction ("colier" -> "collier"), None if unchanged
    understood_by: Literal["rules", "llm"] = "rules"  # llm: the rules understood nothing, Qwen read it


class NextAction(BaseModel):
    """What the orchestrator can do next (same shape as Smart Buy's): chain an agent or ask the user."""

    action: str  # ask_user / open_shop / judge / show_outfits / more_results / feedback
    label: str  # text for a button or for the orchestrator LLM, in the request's language
    tool: str | None = None  # agent to call next: localshop, smartbuy, stylist; None = the app does it
    args: dict = {}


class AgentInfo(BaseModel):
    name: str
    version: str


class LocalShopOutput(BaseModel):
    results: list[ShopResult]
    parsed: ParsedQuery | None = None
    total_matches: int = 0  # products passing the filters, before keeping the top k
    note: str | None = None  # e.g. city filter relaxed because nothing matched there
    search_id: str | None = None  # id of this search in the event log, to send back with clicks
    # --- agent identity + memory
    agent: AgentInfo | None = None
    session_id: str = "default"
    decision_id: str | None = None  # id of this answer in the user's memory, to send back with feedback
    question: str | None = None  # ONE question the user can answer; the orchestrator stops and asks it
    question_key: str | None = None  # gender / max_price_tnd / query: send it back in `answer`
    memory_notes: list[str] = []  # what the agent took from memory for this answer
    next_actions: list[NextAction] = []


class Feedback(BaseModel):
    """Were the results useful? Did the user buy one of them? (long-term memory)"""

    user_id: str
    decision_id: str
    useful: bool | None = None
    bought_product_id: str | None = None


class ClickEvent(BaseModel):
    """The user opened a result (product_view) or went to the shop's website (shop_click)."""

    type: Literal["product_view", "shop_click"]
    product_id: str
    search_id: str | None = Field(None, description="search_id of the search that showed the product")
    shop: str | None = None
    rank: int | None = Field(None, ge=1, description="position of the product in the results, from 1")
    user_id: str | None = None
