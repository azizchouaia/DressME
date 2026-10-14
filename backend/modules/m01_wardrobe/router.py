"""HTTP endpoints of M1. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ClassifyRequest, ClassifyResponse, SimilarRequest, SimilarResponse, ItemsRequest, ItemsResponse

router = APIRouter(prefix="/m01", tags=["M1 Wardrobe digitiser + item database"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    return _impl().classify(req.model_dump())

@router.post("/similar", response_model=SimilarResponse)
def similar(req: SimilarRequest):
    return _impl().similar(req.model_dump())

@router.post("/items", response_model=ItemsResponse)
def items(req: ItemsRequest):
    return _impl().items(req.model_dump())
