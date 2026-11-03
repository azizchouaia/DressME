from fastapi import APIRouter

from app.api.routes import auth, avatar, body, garments, outfits, stylist, users, wardrobe

api_router = APIRouter()
for module in (auth, users, body, wardrobe, outfits, avatar, garments, stylist):
    api_router.include_router(module.router)
