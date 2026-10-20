from fastapi import APIRouter, Depends

from app.api.auth.dependencies import get_current_user
from app.api.auth.router import router as auth_router
from app.api.projects.router import router as projects_router
from app.modules.meta.router import router as meta_router
from app.api.executions.router import router as executions_router

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)

protected_router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

protected_router.include_router(
    meta_router,
    tags=["meta"],
)

protected_router.include_router(
    projects_router,
    prefix="/projects",
    tags=["projects"],
)

protected_router.include_router(
    executions_router,
    prefix="/executions",
    tags=["executions"],
)

api_router.include_router(protected_router)
