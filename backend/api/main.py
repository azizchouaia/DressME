from fastapi import FastAPI

from .routes import chat, health, outfits, smartbuy, tryon, wardrobe

app = FastAPI(title="DressMe API", version="0.1.0")

app.include_router(health.router)
app.include_router(wardrobe.router, prefix="/wardrobe", tags=["wardrobe"])
app.include_router(outfits.router, prefix="/outfits", tags=["outfits"])
app.include_router(smartbuy.router, prefix="/smartbuy", tags=["smartbuy"])
app.include_router(tryon.router, prefix="/tryon", tags=["tryon"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
