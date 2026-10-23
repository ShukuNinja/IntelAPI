from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.projects.schemas import (
    PaginationRead,
    ProjectCreate,
    ProjectListRead,
    ProjectRead,
    ProjectUpdate,
)
from app.db.session import get_db
from app.models.project import Project
from app.models.user import User

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=ProjectListRead)
def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: bool = False,
) -> ProjectListRead:
    filters = [Project.owner_user_id == current_user.id]

    if not include_archived:
        filters.append(Project.deleted_at.is_(None))

    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0

    projects = db.scalars(
        select(Project)
        .where(*filters)
        .order_by(Project.created_at.desc(), Project.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return ProjectListRead(
        items=[ProjectRead.model_validate(project) for project in projects],
        pagination=PaginationRead(
            limit=limit,
            offset=offset,
            total=total,
        ),
    )


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    project = Project(
        owner_user_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectRead.model_validate(project)


def get_owned_project(
    db: Session,
    project_id: UUID,
    owner_user_id: UUID,
) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_user_id == owner_user_id,
            Project.deleted_at.is_(None),
        )
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Project not found.",
            },
        )

    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    project = get_owned_project(db, project_id, current_user.id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "At least one project field must be supplied.",
            },
        )

    if "name" in payload.model_fields_set and payload.name is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Project name cannot be null.",
            },
        )

    project = get_owned_project(db, project_id, current_user.id)

    if "name" in payload.model_fields_set:
        project_name = payload.name

        if project_name is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Project name cannot be null.",
                },
            )

        project.name = project_name

    if "description" in payload.model_fields_set:
        project.description = payload.description

    db.commit()
    db.refresh(project)

    return ProjectRead.model_validate(project)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectRead,
)
def archive_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectRead:
    project = get_owned_project(db, project_id, current_user.id)
    project.deleted_at = datetime.now(UTC)

    db.commit()
    db.refresh(project)

    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Remove a project from active workspaces while retaining its archived records."""
    project = get_owned_project(db, project_id, current_user.id)
    project.deleted_at = datetime.now(UTC)
    db.commit()
