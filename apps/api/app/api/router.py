from fastapi import APIRouter, Depends

from app.api.auth.dependencies import get_current_user
from app.api.auth.router import router as auth_router
from app.api.campaigns.router import router as campaigns_router
from app.api.collections.router import router as collections_router
from app.api.environments.router import router as environments_router
from app.api.executions.persisted_router import (
    router as persisted_executions_router,
)
from app.api.executions.router import router as executions_router
from app.api.experiments.router import router as experiments_router
from app.api.findings.router import router as findings_router
from app.api.health_checks.router import router as health_checks_router
from app.api.projects.router import router as projects_router
from app.api.requests.router import router as requests_router
from app.api.specifications.router import router as specifications_router
from app.modules.meta.router import router as meta_router

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)

protected_router = APIRouter(dependencies=[Depends(get_current_user)])

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
    tags=["executions"],
)

# The collections router defines its own complete paths.
protected_router.include_router(
    collections_router,
    tags=["collections"],
)

protected_router.include_router(
    requests_router,
    tags=["saved-requests"],
)

protected_router.include_router(
    environments_router,
    tags=["environments"],
)

protected_router.include_router(
    persisted_executions_router,
    tags=["persisted-executions"],
)

protected_router.include_router(
    specifications_router,
    tags=["specifications"],
)

protected_router.include_router(
    health_checks_router,
    tags=["health-checks"],
)

protected_router.include_router(
    campaigns_router,
    tags=["campaigns"],
)

protected_router.include_router(
    experiments_router,
    tags=["experiments"],
)

protected_router.include_router(
    findings_router,
    tags=["findings"],
)

api_router.include_router(protected_router)
