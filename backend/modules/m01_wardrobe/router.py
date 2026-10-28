"""HTTP endpoints of M1. Included automatically by api/main.py.

Serves mock.py when settings.use_mocks is true (default), service.py otherwise.
Also serves the wardrobe demo UI on GET /m01/ui and the locally stored images on GET /m01/media/...
"""

import stat
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from shared.config import settings

from . import mock, service, storage
from .config import use_mocks
from .contract import (
    ClassifyRequest,
    ClassifyResponse,
    DeleteResponse,
    DocumentRequest,
    DocumentResponse,
    DonateRequest,
    DonationSuggestionsRequest,
    DonationSuggestionsResponse,
    DuplicatesRequest,
    DuplicatesResponse,
    ExtractionUnavailableError,
    InvalidImageError,
    InvalidUpdateError,
    ItemNotFoundError,
    ItemsRequest,
    ItemsResponse,
    ItemUpdate,
    SimilarRequest,
    SimilarResponse,
    WardrobeItem,
)

router = APIRouter(prefix="/m01", tags=["M1 Wardrobe digitiser + item database"])

UI_DIR = Path(__file__).resolve().parent / "ui"
T = TypeVar("T")


def _impl():
    return mock if use_mocks(getattr(settings, "use_mocks", True)) else service


async def _call(result: Awaitable[T]) -> T:
    try:
        return await result
    except ItemNotFoundError as e:
        raise HTTPException(404, f"item not found: {e}") from e
    except (InvalidImageError, InvalidUpdateError) as e:
        raise HTTPException(422, str(e)) from e
    except ExtractionUnavailableError as e:
        raise HTTPException(503, f"document extraction unavailable: {e}") from e


@router.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    return await _call(_impl().classify(req))


@router.post("/similar", response_model=SimilarResponse)
async def similar(req: SimilarRequest):
    return await _call(_impl().similar(req))


@router.post("/duplicates", response_model=DuplicatesResponse)
async def duplicates(req: DuplicatesRequest):
    return await _call(_impl().duplicates(req))


@router.post("/items", response_model=ItemsResponse)
async def items(req: ItemsRequest):
    return await _call(_impl().items(req))


@router.get("/items/{item_id}", response_model=WardrobeItem)
async def get_item(item_id: str, user_id: str = Query(min_length=1)):
    return await _call(_impl().get_item(user_id, item_id))


@router.post("/items/{item_id}/confirm", response_model=WardrobeItem)
async def confirm_item(item_id: str, user_id: str = Query(min_length=1)):
    """Accept a pending item (possible duplicate held by /classify). To cancel instead: DELETE /items/{id}."""
    return await _call(_impl().confirm_item(user_id, item_id))


@router.post("/items/{item_id}/donation-suggestions", response_model=DonationSuggestionsResponse)
async def donation_suggestions(
    item_id: str, req: DonationSuggestionsRequest | None = None, user_id: str = Query(min_length=1)
):
    """Where to give this piece: places of the verified list (donation_places.json), picked and explained by
    the local LLM. Without Ollama, the list's own order and text (llm_used=false). Nothing is saved."""
    from . import donation

    item = await _call(_impl().get_item(user_id, item_id))
    return await donation.suggest(item, (req or DonationSuggestionsRequest()).city)


@router.post("/items/{item_id}/donate", response_model=WardrobeItem)
async def donate_item(item_id: str, req: DonateRequest | None = None, user_id: str = Query(min_length=1)):
    """Puts the piece in the 'À donner' bag (status donated). It leaves /items, M2 and M5.
    The bag: POST /items with status=donated. 422 for a pending or already given piece."""
    return await _call(_impl().donate_item(user_id, item_id, req or DonateRequest()))


@router.patch("/items/{item_id}", response_model=WardrobeItem)
async def update_item(item_id: str, update: ItemUpdate, user_id: str = Query(min_length=1)):
    """Form: size, price, brand, purchase, composition, condition, notes, receipt image, AI corrections."""
    return await _call(_impl().update_item(user_id, item_id, update))


@router.post("/documents/extract", response_model=DocumentResponse)
async def extract_document(req: DocumentRequest):
    """Receipt / price tag / care label -> proposed fields (through M8). Nothing is saved."""
    return await _call(_impl().extract_document(req))


@router.delete("/items/{item_id}", response_model=DeleteResponse)
async def delete_item(item_id: str, user_id: str = Query(min_length=1)):
    return await _call(_impl().delete_item(user_id, item_id))


# --- static files ---------------------------------------------------------------------------------
# FastAPI's include_router drops Mount routes, so StaticFiles is used through lookup_path()
# (which also blocks path traversal) instead of router.mount().

def _serve(directory: Path, path: str) -> FileResponse:
    full, st = StaticFiles(directory=directory, check_dir=False).lookup_path(path)
    if st is None or not stat.S_ISREG(st.st_mode):
        raise HTTPException(404)
    return FileResponse(full, headers={"Cache-Control": "no-cache"})


@router.get("/ui", include_in_schema=False)
async def ui_index():
    return _serve(UI_DIR, "index.html")


@router.get("/ui/", include_in_schema=False)
async def ui_index_slash():
    return RedirectResponse("/m01/ui")


@router.get("/ui/{path:path}", include_in_schema=False)
async def ui_file(path: str):
    return _serve(UI_DIR, path)


@router.get("/media/{path:path}", include_in_schema=False)
async def media_file(path: str):
    return _serve(storage.media_root(), path)
