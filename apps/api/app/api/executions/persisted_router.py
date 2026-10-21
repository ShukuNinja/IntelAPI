from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth.dependencies import get_current_user
from app.api.executions.persisted_schemas import (
    ExecutionCreate,
    ExecutionListRead,
    ExecutionRead,
)
from app.db.session import get_db
from app.models.execution import Execution
from app.models.project import Project
from app.models.saved_request import SavedRequest
from app.models.user import User
from app.modules.execution.service import execute_saved_request

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Resource not found."}
    )


@router.post("/requests/{request_id}/execute", response_model=ExecutionRead, status_code=201)
def run_saved_request(
    request_id: UUID, payload: ExecutionCreate, db: DbSession, current_user: CurrentUser
) -> ExecutionRead:
    saved_request = db.scalar(
        select(SavedRequest)
        .join(Project, SavedRequest.project_id == Project.id)
        .where(
            SavedRequest.id == request_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if saved_request is None:
        raise _not_found()
    execution = execute_saved_request(
        db, saved_request, current_user.id, payload.environment_id, payload.timeout_seconds
    )
    loaded = db.scalar(
        select(Execution)
        .options(selectinload(Execution.evidence))
        .where(Execution.id == execution.id)
    )
    assert loaded is not None
    return ExecutionRead.model_validate(loaded)


@router.get("/executions/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser) -> ExecutionRead:
    execution = db.scalar(
        select(Execution)
        .join(Project, Execution.project_id == Project.id)
        .options(selectinload(Execution.evidence))
        .where(
            Execution.id == execution_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if execution is None:
        raise _not_found()
    return ExecutionRead.model_validate(execution)


@router.get("/projects/{project_id}/executions", response_model=ExecutionListRead)
def list_executions(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionListRead:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise _not_found()
    total = (
        db.scalar(
            select(func.count()).select_from(Execution).where(Execution.project_id == project_id)
        )
        or 0
    )
    rows = (
        db.scalars(
            select(Execution)
            .options(selectinload(Execution.evidence))
            .where(Execution.project_id == project_id)
            .order_by(Execution.created_at.desc(), Execution.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )
    return ExecutionListRead(
        items=[ExecutionRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
