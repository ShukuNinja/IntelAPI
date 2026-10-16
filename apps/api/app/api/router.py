from fastapi import APIRouter
from app.modules.meta.router import router as meta_router

api_router = APIRouter()
api_router.include_router(meta_router, tags=["meta"])
