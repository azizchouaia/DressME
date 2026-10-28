"""M13 Partner commerce links: buy links + promo codes for a type / colour."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/m13", tags=["M13 Partner commerce links"])
DATA = Path(__file__).resolve().parents[3] / "ml" / "data" / "bo5"


class LinksRequest(BaseModel):
    subcategory: str
    colour: str
    max_price_tnd: float | None = None
    k: int = 3


@router.post("/links")
def links(req: LinksRequest):
    return {"links": service.links(service.load(DATA), req.subcategory, req.colour, req.max_price_tnd, req.k)}


class ClickRequest(BaseModel):
    product_id: str
    shop: str | None = None
    user_id: str | None = None
    rank: int | None = None
    search_id: str | None = None


@router.post("/click")
def click(req: ClickRequest):
    """The user tapped a buy link (BO5 KPI). Logged in M7's event log."""
    return {"logged": service.log_click(req.product_id, req.shop, req.user_id, req.rank, req.search_id)}


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
