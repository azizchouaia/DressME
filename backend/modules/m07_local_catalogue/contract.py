"""Input/output of the LocalShopAgent (M7 Local catalogue). Built from shared schemas."""

from pydantic import BaseModel, Field, model_validator

from shared.schemas import GarmentCategory


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
    k: int = Field(10, ge=1, le=50)

    @model_validator(mode="after")
    def _something_to_search(self):
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
    max_price_tnd: float | None = None
    min_price_tnd: float | None = None
    city: str | None = None
    governorate: str | None = None
    terms: list[str] = []
    prompt_en: str | None = None
    corrected: str | None = None  # request after typo correction ("colier" -> "collier"), None if unchanged


class LocalShopOutput(BaseModel):
    results: list[ShopResult]
    parsed: ParsedQuery | None = None
    total_matches: int = 0  # products passing the filters, before keeping the top k
    note: str | None = None  # e.g. city filter relaxed because nothing matched there
