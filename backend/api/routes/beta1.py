"""Beta 1 demo: every finished BO in one phone page, around the 3D avatar.

/beta1/demo       the page (body -> bare avatar -> wardrobe of ready-to-wear 3D pieces -> M2 recommendations
                  put on the avatar, swap by drag and drop; wear log / laundry via M3; tabs for M4 and M17)
/beta1/recommend  M2 on the user's own 3D pieces (M1 Garment format + FashionCLIP vectors from M9's wardrobe)
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/beta1", tags=["beta 1 demo"])
PAGE = Path(__file__).resolve().parents[2] / "modules" / "m09_avatar_3d" / "demo" / "beta1.html"


class RecommendIn(BaseModel):
    user_id: str = "me"
    occasion: str = "casual"
    mood: str | None = None
    city: str = "Tunis"
    n: int = 3
    action: str = "recommend"  # recommend / complete (keep pinned pieces, fill the rest)
    pinned_item_ids: list[str] = []
    exclude_item_ids: list[str] = []


@router.get("/demo", include_in_schema=False)
def page():
    return FileResponse(PAGE)


@router.post("/recommend")
def recommend(req: RecommendIn):
    from modules.m02_recommendation import service as m2
    from modules.m09_avatar_3d import service as m9
    from modules.m09_avatar_3d import wardrobe3d

    user = m9._uid(req.user_id)
    items = wardrobe3d.wardrobe_items(user)
    if len(items) < 2:
        raise HTTPException(400, "add at least a top and a bottom (or a dress) to your pieces first")
    payload = {
        "items": items,
        "context": {"occasion": req.occasion, "mood": req.mood, "city": req.city},
        "options": {"n": req.n, "exclude_item_ids": req.exclude_item_ids},
    }
    if req.action == "complete":
        out = m2.complete({"user_id": user, "payload": {**payload, "pinned_item_ids": req.pinned_item_ids}})
    else:
        out = m2.recommend({"user_id": user, "payload": payload})
    res = out["result"]
    return {
        "result": {
            "outfits": res.get("outfits", []),
            "context": res.get("context"),
            "weather_source": res.get("weather_source"),
            "wear_log_source": res.get("wear_log_source"),
        },
        "mocked": False,
    }
