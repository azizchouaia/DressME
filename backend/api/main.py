"""API gateway: includes every module router automatically (modules/*/router.py)."""

import importlib
import pkgutil
from pathlib import Path

from dotenv import load_dotenv

# infra/.env -> os.environ, so module switches (M01_USE_MOCKS, M03_DATABASE_URL...) work without exporting them
load_dotenv(Path(__file__).resolve().parents[2] / "infra" / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import modules

from .routes import agents, auth, beta1, bo_demo, chat, health

app = FastAPI(title="DressMe API", version="0.2.0")


@app.exception_handler(NotImplementedError)
async def _not_built(request, exc):  # a module whose real code is not written yet (no mock in the app)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=501, content={
        "detail": "not available yet: this module's real code is still to come from its owner",
        "available": False, "path": request.url.path})
# Local development: the Flutter web app (flutter run -d chrome) runs on another localhost port.
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router, prefix="/chat", tags=["chat (BO8)"])
app.include_router(beta1.router)
app.include_router(agents.router)
app.include_router(bo_demo.router)

# BO9 (Nadhir): the SMPL-X avatar studio (avatar_studio/web). The viewer loads its bodies from the site root
# (/presets/<sex>_<build>.glb, /prototypes/<sex>.jpg), so these folders are served at the root.
_STUDIO = Path(__file__).resolve().parents[2] / "avatar_studio" / "web"
if _STUDIO.is_dir():
    from fastapi.staticfiles import StaticFiles

    for _name in ("viewer", "presets", "prototypes", "users"):
        if (_STUDIO / _name).is_dir():
            app.mount(f"/{_name}", StaticFiles(directory=_STUDIO / _name, html=True), name=f"bo9_{_name}")

for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
    try:
        mod = importlib.import_module(f"modules.{m.name}.router")
    except ModuleNotFoundError as e:
        if e.name != f"modules.{m.name}.router":
            raise
        continue
    app.include_router(mod.router)
