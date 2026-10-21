"""HTTP endpoints of M9. Included automatically by api/main.py."""

import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shared.config import settings

from . import mock, service, wardrobe3d
from .contract import Body, PieceSheet, RenderRequest, RenderResponse

router = APIRouter(prefix="/m09", tags=["M9 3D avatar renderer"])
DEMO = Path(__file__).parent / "demo"


def _impl():
    """M09_USE_MOCK overrides the global USE_MOCKS for M9 only."""
    flag = os.environ.get("M09_USE_MOCK")
    use_mock = settings.use_mocks if flag is None else flag.lower() in ("1", "true", "yes")
    return mock if use_mock else service


def _err(fn, *a, **k):
    """Errors always come back as JSON {"detail": ...} so the page can show them."""
    try:
        return fn(*a, **k)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e


@router.post("/render", response_model=RenderResponse)
def render(req: RenderRequest):
    """Body (sex, height, weight) + piece ids -> GLB url of the dressed faceless avatar (cached)."""
    return _err(_impl().render, req.model_dump())


@router.post("/pieces")
async def create_piece(
    user_id: str = Form("anonymous"),
    type: str = Form("t-shirt"),  # noqa: A002
    size: str = Form("M"),
    fit: str = Form("regular"),
    gsm: str = Form(""),
    length: str = Form(""),
    sleeves: str = Form(""),
    color: str = Form(""),
    name: str = Form(""),
    front: UploadFile | None = File(None),  # noqa: B008  (FastAPI's way to declare uploads)
    back: UploadFile | None = File(None),  # noqa: B008
):
    """A piece = front photo (+ optional back photo) + its sheet. Without photo, give a colour."""
    sheet = PieceSheet(
        type=type,
        size=size or None,
        fit=fit,
        gsm=float(gsm) if gsm else None,
        length=length or None,
        sleeves=sleeves or None,
        color=color or None,
        name=name or None,
    )
    f = await front.read() if front and front.filename else None
    b = await back.read() if back and back.filename else None

    def ext(u):
        return (os.path.splitext(u.filename)[1] or ".jpg").lower() if u and u.filename else ".jpg"

    return _err(service.create_piece, user_id, sheet, f, b, ext(front), ext(back))


@router.get("/pieces")
def list_pieces(user_id: str = "anonymous"):
    return service.list_pieces(user_id)


@router.put("/pieces/{piece_id}")
def update_piece(piece_id: str, sheet: PieceSheet, user_id: str = "anonymous"):
    """Change the sheet of a piece (size, fit, grammage, length...) without re-taking the photo."""
    return _err(service.update_piece, user_id, piece_id, sheet)


@router.delete("/pieces/{piece_id}")
def delete_piece(piece_id: str, user_id: str = "anonymous"):
    return service.delete_piece(user_id, piece_id)


@router.get("/wardrobe3d")
def wardrobe_3d(user_id: str = "anonymous"):
    """The user's body + every piece with its ready-to-wear 3D garment (glb_url) or its build status."""
    return {"result": wardrobe3d.state(user_id), "mocked": False}


class OutfitIn(BaseModel):
    user_id: str = "anonymous"
    piece_ids: list[str] = []
    animate: bool = False


@router.post("/outfit3d")
def outfit_3d(req: OutfitIn):
    """Pieces worn together, re-fitted over each other with cloth physics (cached per combination); with
    `animate`, the turn animation (morph targets). Status queued / building / ready; poll until ready."""
    return {"result": _err(wardrobe3d.outfit, req.user_id, req.piece_ids, req.animate), "mocked": False}


@router.post("/body")
def set_body(body: Body, user_id: str = "anonymous"):
    """Save the user's body; the bare avatar and every piece are (re)built for it in the background."""
    user = service._uid(user_id)
    wardrobe3d.set_profile(user, body)
    wardrobe3d.request(user)
    return {"result": wardrobe3d.state(user), "mocked": False}


@router.get("/options")
def options():
    """Garment types, sizes, fits, lengths, default grammages; whether Blender / the photo env are found."""
    return {"result": service.options(), "mocked": False}


@router.get("/files/{path:path}", include_in_schema=False)
def files(path: str):
    full = (service.DATA / path).resolve()
    if service.DATA.resolve() not in full.parents or not full.is_file():
        raise HTTPException(404)
    media = "model/gltf-binary" if full.suffix == ".glb" else None
    return FileResponse(full, media_type=media)


@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(DEMO / "index.html")
