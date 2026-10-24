import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.secret_storage import (
    SecretStorageError,
    decrypt_environment_values,
    encrypt_environment_values,
)
from app.db.session import get_db
from app.models import Environment, Project, User
from app.models.execution import ExecutionRecord
from app.modules.execution.service import (
    ExecutionError,
    execute_request,
    resolve_and_validate,
    validate_url_syntax,
)
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}/executions", tags=["execution"])

SSRF_DEMO_TARGETS = [
    ("Loopback development exception", "http://127.0.0.1/"),
    ("Private network address", "http://10.0.0.8/"),
    ("Link-local metadata address", "http://169.254.169.254/latest/meta-data/"),
    ("Reserved documentation address", "http://192.0.2.1/"),
    ("Public address control", "http://8.8.8.8/"),
]


class ExecuteRequest(BaseModel):
    method: Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
    url: str = Field(min_length=8, max_length=4096)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: str | None = Field(default=None, max_length=1_000_000)
    confirm_unsafe: bool = False
    environment_id: UUID | None = None


@router.get("/ssrf-demo")
async def run_ssrf_policy_demo(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Preflight fixed demonstration addresses without making any HTTP requests."""
    _owned_project(db, project_id)
    cases = []
    for name, target_url in SSRF_DEMO_TARGETS:
        hostname, _ = validate_url_syntax(target_url)
        try:
            await resolve_and_validate(hostname)
        except ExecutionError as exc:
            decision = "blocked_by_policy"
            reason = str(exc)
        else:
            decision = "allowed_by_policy"
            reason = (
                "Loopback is allowed by the local-development setting. No HTTP request was sent."
                if name == "Loopback development exception"
                else "The destination passed the current address policy. No HTTP request was sent."
            )
        cases.append(
            {
                "name": name,
                "target_url": target_url,
                "protected_decision": decision,
                "protected_reason": reason,
                "without_protection_simulation": (
                    "A vulnerable client would attempt this destination; the demo does not send it."
                ),
                "network_request_sent": False,
            }
        )
    return {
        "protection_active": True,
        "local_targets_allowed": get_settings().allow_local_targets,
        "private_network_targets_allowed": get_settings().allow_private_network_targets,
        "network_requests_sent": 0,
        "cases": cases,
    }


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
    resolved_url = payload.url
    resolved_headers = payload.headers
    resolved_body = payload.body
    if payload.environment_id is not None:
        environment = db.scalar(
            select(Environment).where(
                Environment.id == payload.environment_id,
                Environment.project_id == project_id,
            )
        )
        if environment is None:
            raise HTTPException(status_code=404, detail="Environment not found in this project.")
        if not environment.secrets_migrated:
            try:
                migrated = encrypt_environment_values(environment.variables)
            except SecretStorageError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            environment.secret_variables = {**environment.secret_variables, **migrated}
            environment.variables = {}
            environment.secrets_migrated = True
            db.commit()
        try:
            variables = {
                **environment.variables,
                **decrypt_environment_values(environment.secret_variables),
            }
        except SecretStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if environment.base_url:
            variables["baseUrl"] = environment.base_url

        def interpolate(value: str) -> str:
            def replace(match: re.Match[str]) -> str:
                key = match.group(1)
                if key not in variables:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Environment variable '{key}' is not defined.",
                    )
                return variables[key]

            return re.sub(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}", replace, value)

        resolved_url = interpolate(resolved_url)
        resolved_headers = {key: interpolate(value) for key, value in resolved_headers.items()}
        resolved_body = interpolate(resolved_body) if resolved_body is not None else None
        resolved_request = resolved_url + str(resolved_headers) + (resolved_body or "")
        if re.search(r"\{\{[^{}]+\}\}", resolved_request):
            raise HTTPException(
                status_code=422,
                detail="An environment template variable could not be resolved.",
            )
    started_at = datetime.now(UTC)
    safe_snapshot: dict[str, str] = {"method": payload.method, "origin": "blocked"}
    try:
        result = await execute_request(
            method=payload.method,
            url=resolved_url,
            headers=resolved_headers,
            body=resolved_body,
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
