"""Input/output of the LocalShopAgent. Built from shared schemas."""

from pydantic import BaseModel

class LocalShopInput(BaseModel):
    query: str
    gap: str | None = None
    city: str | None = "Tunis"
    max_price_tnd: float | None = None
    style_vector: list[float] | None = None


class ShopResult(BaseModel):
    shop: str
    area: str | None = None
    item: str
    price_tnd: float | None = None
    match: float


class LocalShopOutput(BaseModel):
    results: list[ShopResult]
