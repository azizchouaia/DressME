"""Owner: BO7 · serves the Flutter web build of the DressMe app on the API's address: http://localhost:8000/bo7/app/

Same origin as the API, so the app calls /m10, /m15, /bo7 without any CORS setting, and the BO9 avatar viewer
(/bo7/avatar/viewer/) can be photographed from the app. Build it once from mobile/:

    flutter build web --base-href /bo7/app/

Unknown paths return index.html (the app's own router handles them).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

BUILD = Path(__file__).resolve().parents[3] / "mobile" / "build" / "web"
router = APIRouter(prefix="/bo7/app", tags=["BO7 Flutter app"])


@router.get("/{name:path}", include_in_schema=False)
async def app_file(name: str = ""):
    if not (BUILD / "index.html").exists():
        raise HTTPException(
            404, "Flutter web build not found: in mobile/, run  flutter build web --base-href /bo7/app/"
        )
    p = (BUILD / name).resolve()
    if name and BUILD.resolve() in p.parents and p.is_file():
        return FileResponse(p)
    return FileResponse(BUILD / "index.html", headers={"Cache-Control": "no-cache"})
