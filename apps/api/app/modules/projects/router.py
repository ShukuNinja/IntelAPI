import hashlib
import json
from typing import Annotated, Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Project, User
from app.models.specification import ApiSpecification
from app.modules.api_understanding.router import SpecificationInput
from app.modules.api_understanding.service import (
    SpecificationError,
    parse_specification,
    parse_specification_content,
)

router = APIRouter(tags=["projects"])
LOCAL_USER_SUB = "intelapi-local-single-user"


def _require_local_mode() -> None:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503,
            detail=(
                "Local single-user projects are disabled in production until "
                "authentication is configured."
            ),
        )


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


def _local_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    if user is None:
        user = User(google_sub=LOCAL_USER_SUB, display_name="Local user")
        db.add(user)
        db.flush()
    return user


def _redact_source_url(source_url: str | None) -> str | None:
    if source_url is None:
        return None
    parsed = urlsplit(source_url)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    authority = f"{hostname}:{port}" if port is not None else hostname
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


@router.get("/projects")
def list_projects(db: Annotated[Session, Depends(get_db)]) -> list[dict[str, Any]]:
    _require_local_mode()
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    if user is None:
        return []
    return [
        {"id": str(project.id), "name": project.name, "description": project.description}
        for project in db.scalars(
            select(Project)
            .where(Project.owner_user_id == user.id, Project.deleted_at.is_(None))
            .order_by(Project.created_at)
        )
    ]


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    _require_local_mode()
    user = _local_user(db)
    project = Project(
        owner_user_id=user.id, name=payload.name.strip(), description=payload.description
    )
    if not project.name:
        raise HTTPException(status_code=422, detail="Project name cannot be blank.")
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": str(project.id), "name": project.name, "description": project.description}


@router.post("/projects/{project_id}/specifications/import", status_code=status.HTTP_201_CREATED)
def import_specification(
    project_id: UUID, payload: SpecificationInput, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    _require_local_mode()
    user = _local_user(db)
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_user_id == user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        if payload.document is not None:
            document = payload.document
            normalized = parse_specification(document)
            source_format = "json"
        else:
            source = payload.content or ""
            source_format = payload.source_format
            normalized = parse_specification_content(source, source_format)
            import yaml

            document = json.loads(source) if source_format == "json" else yaml.safe_load(source)
    except SpecificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    document = json.loads(json.dumps(document, default=str))
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    spec = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.project_id == project.id,
            ApiSpecification.content_hash == digest,
        )
    )
    created = spec is None
    if spec is None:
        spec = ApiSpecification(
            project_id=project.id,
            title=normalized["specification"]["title"],
            spec_version=normalized["specification"]["version"],
            source_format=source_format,
            source_url=_redact_source_url(str(payload.source_url) if payload.source_url else None),
            content_hash=digest,
            source_document=document,
            normalized_operations=normalized["operations"],
        )
        db.add(spec)
        db.commit()
        db.refresh(spec)
    elif spec.source_url is None and payload.source_url is not None:
        spec.source_url = _redact_source_url(str(payload.source_url))
        db.commit()
        db.refresh(spec)
    return {
        "id": str(spec.id),
        "project_id": str(spec.project_id),
        "title": spec.title,
        "version": spec.spec_version,
        "source_url": spec.source_url,
        "content_hash": spec.content_hash,
        "created": created,
        "operations": spec.normalized_operations,
    }


@router.get("/projects/{project_id}/specifications")
def list_specifications(
    project_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> list[dict[str, Any]]:
    _require_local_mode()
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    project = (
        db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user.id))
        if user
        else None
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return [
        {
            "id": str(spec.id),
            "title": spec.title,
            "version": spec.spec_version,
            "content_hash": spec.content_hash,
            "source_url": spec.source_url,
            "created_at": spec.created_at.isoformat(),
            "operation_count": len(spec.normalized_operations),
        }
        for spec in db.scalars(
            select(ApiSpecification)
            .where(ApiSpecification.project_id == project.id)
            .order_by(ApiSpecification.created_at.desc())
        )
    ]


@router.get("/projects/{project_id}/specifications/{specification_id}")
def get_specification(
    project_id: UUID, specification_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    _require_local_mode()
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    project = (
        db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user.id))
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
        "id": str(specification.id),
        "title": specification.title,
        "version": specification.spec_version,
        "source_format": specification.source_format,
        "source_url": specification.source_url,
        "document": specification.source_document,
        "operations": specification.normalized_operations,
    }
