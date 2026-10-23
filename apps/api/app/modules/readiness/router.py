from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import ApiSpecification, Project, User
from app.modules.projects.router import LOCAL_USER_SUB
from app.modules.readiness.service import analyze_readiness

router = APIRouter(prefix="/projects/{project_id}/specifications", tags=["readiness"])


@router.get("/{specification_id}/readiness")
def get_readiness(
    project_id: UUID,
    specification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(status_code=503, detail="Local analysis is disabled in production.")
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    project = (
        db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.owner_user_id == user.id,
                Project.deleted_at.is_(None),
            )
        )
        if user
        else None
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id,
            ApiSpecification.project_id == project.id,
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    return {
        "project_id": str(project.id),
        "specification_id": str(specification.id),
        "specification": {
            "title": specification.title,
            "version": specification.spec_version,
            "content_hash": specification.content_hash,
        },
        **analyze_readiness(specification.source_document, specification.normalized_operations),
    }
