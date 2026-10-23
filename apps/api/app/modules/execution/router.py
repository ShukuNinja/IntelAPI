from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Project, User
from app.models.execution import ExecutionRecord
from app.modules.execution.service import ExecutionError, execute_request
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}/executions", tags=["execution"])


class ExecuteRequest(BaseModel):
    method: Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
    url: str = Field(min_length=8, max_length=4096)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: str | None = Field(default=None, max_length=1_000_000)
    confirm_unsafe: bool = False


def _owned_project(db: Session, project_id: UUID) -> Project:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503,
            detail=(
                "Local single-user execution is disabled in production until "
                "authentication is configured."
            ),
        )
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
    return project


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_execution(
    project_id: UUID,
    payload: ExecuteRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    _owned_project(db, project_id)
    started_at = datetime.now(UTC)
    safe_snapshot: dict[str, str] = {"method": payload.method, "origin": "blocked"}
    try:
        result = await execute_request(
            method=payload.method,
            url=payload.url,
            headers=payload.headers,
            body=payload.body,
            confirm_unsafe=payload.confirm_unsafe,
        )
        safe_snapshot["origin"] = result["origin"]
    except ExecutionError as exc:
        completed_at = datetime.now(UTC)
        record = ExecutionRecord(
            project_id=project_id,
            outcome=exc.outcome,
            request_snapshot=safe_snapshot,
            started_at=started_at,
            completed_at=completed_at,
            error_summary=str(exc)[:500],
        )
        db.add(record)
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    completed_at = datetime.now(UTC)
    record = ExecutionRecord(
        project_id=project_id,
        outcome=result["outcome"],
        request_snapshot=safe_snapshot,
        status_code=result["status_code"],
        duration_ms=result["elapsed_ms"],
        response_headers=result["headers"],
        response_size_bytes=result["response_bytes"],
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    result["id"] = str(record.id)
    result["created_at"] = record.started_at.isoformat()
    return result


@router.get("")
def list_executions(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    project = _owned_project(db, project_id)
    bounded_limit = max(1, min(limit, 100))
    return [
        {
            "id": str(record.id),
            "method": record.request_snapshot.get("method", ""),
            "origin": record.request_snapshot.get("origin", ""),
            "candidate_id": record.request_snapshot.get("candidate_id"),
            "status_code": record.status_code,
            "elapsed_ms": record.duration_ms,
            "response_bytes": record.response_size_bytes,
            "outcome": record.outcome,
            "error_summary": record.error_summary,
            "created_at": record.started_at.isoformat(),
        }
        for record in db.scalars(
            select(ExecutionRecord)
            .where(ExecutionRecord.project_id == project.id)
            .order_by(ExecutionRecord.started_at.desc())
            .limit(bounded_limit)
        )
    ]
