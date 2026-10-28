"""API gateway: includes every module router automatically (modules/*/router.py)."""

import importlib
import pkgutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import modules

from .routes import agents, beta1, bo_demo, chat, health

app = FastAPI(title="DressMe API", version="0.2.0")
# Local development: the Flutter web app (flutter run -d chrome) runs on another localhost port.
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(chat.router, prefix="/chat", tags=["chat (BO8)"])
app.include_router(beta1.router)
app.include_router(agents.router)
app.include_router(bo_demo.router)

for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
    try:
        mod = importlib.import_module(f"modules.{m.name}.router")
    except ModuleNotFoundError as e:
        if e.name != f"modules.{m.name}.router":
            raise
        continue
    app.include_router(mod.router)
