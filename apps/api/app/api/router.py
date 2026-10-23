from fastapi import APIRouter

from app.modules.api_understanding.router import (
    discovery_router,
)
from app.modules.api_understanding.router import (
    router as specifications_router,
)
from app.modules.client.router import router as client_resources_router
from app.modules.execution.router import router as execution_router
from app.modules.findings.router import router as findings_router
from app.modules.health_checks.router import router as health_checks_router
from app.modules.meta.router import router as meta_router
from app.modules.projects.router import router as projects_router
from app.modules.readiness.router import router as readiness_router
from app.modules.test_generation.router import router as test_generation_router

api_router = APIRouter()
api_router.include_router(meta_router, tags=["meta"])
api_router.include_router(specifications_router)
api_router.include_router(discovery_router)
api_router.include_router(projects_router)
api_router.include_router(execution_router)
api_router.include_router(client_resources_router)
api_router.include_router(readiness_router)
api_router.include_router(findings_router)
api_router.include_router(health_checks_router)
api_router.include_router(test_generation_router)
