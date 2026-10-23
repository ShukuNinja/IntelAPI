from fastapi import APIRouter

from app.modules.meta.router import router as meta_router
from app.modules.api_understanding.router import router as specifications_router

api_router = APIRouter()
api_router.include_router(meta_router, tags=["meta"])
api_router.include_router(specifications_router)
