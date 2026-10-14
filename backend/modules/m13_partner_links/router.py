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
