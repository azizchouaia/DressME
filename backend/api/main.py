"""API gateway: includes every module router automatically (modules/*/router.py)."""

import importlib
import pkgutil

from fastapi import FastAPI

import modules

from .routes import chat, health

app = FastAPI(title="DressMe API", version="0.2.0")
app.include_router(health.router)
app.include_router(chat.router, prefix="/chat", tags=["chat (BO8)"])

for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
    try:
        mod = importlib.import_module(f"modules.{m.name}.router")
    except ModuleNotFoundError as e:
        if e.name != f"modules.{m.name}.router":
            raise
        continue
    app.include_router(mod.router)
