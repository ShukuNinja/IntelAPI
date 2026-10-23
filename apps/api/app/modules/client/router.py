import re
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.secret_storage import SecretStorageError, encrypt_environment_values
from app.db.session import get_db
from app.models import Environment, Project, SavedRequest, User
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}", tags=["request-resources"])
_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _project(db: Session, project_id: UUID) -> Project:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503, detail="Local single-user resources are disabled in production."
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


class SavedRequestInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    collection_name: str | None = Field(default=None, max_length=120)
    method: Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
    url: str = Field(min_length=8, max_length=4096)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: str | None = Field(default=None, max_length=1_000_000)

    @field_validator("name", "collection_name")
    @classmethod
    def strip_names(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        if value == "":
            raise ValueError("Names cannot be blank.")
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        if any(not name.strip() or "\r" in name or "\n" in name for name in headers):
            raise ValueError("Header names must be non-empty and cannot contain line breaks.")
        if any("\r" in value or "\n" in value for value in headers.values()):
            raise ValueError("Header values cannot contain line breaks.")
        return headers


class EnvironmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=2048)
    variables: dict[str, str] = Field(default_factory=dict, max_length=100)
    secrets: dict[str, str] = Field(default_factory=dict, max_length=100)
    remove_secrets: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Environment name cannot be blank.")
        return value

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, variables: dict[str, str]) -> dict[str, str]:
        if any(not _VARIABLE_NAME.fullmatch(key) for key in variables):
            raise ValueError("Variable names must use letters, digits, and underscores.")
        if any(len(value) > 4096 for value in variables.values()):
            raise ValueError("Environment values cannot exceed 4096 characters.")
        return variables

    @field_validator("secrets")
    @classmethod
    def validate_secrets(cls, secrets: dict[str, str]) -> dict[str, str]:
        if any(not _VARIABLE_NAME.fullmatch(key) for key in secrets):
            raise ValueError("Secret names must use letters, digits, and underscores.")
        if any(len(value) > 4096 for value in secrets.values()):
            raise ValueError("Environment secret values cannot exceed 4096 characters.")
        return secrets

    @field_validator("remove_secrets")
    @classmethod
    def validate_remove_secrets(cls, names: list[str]) -> list[str]:
        if any(not _VARIABLE_NAME.fullmatch(name) for name in names):
            raise ValueError("Secret names must use letters, digits, and underscores.")
        return names


def _saved_response(record: SavedRequest) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "name": record.name,
        "collection_name": record.collection_name,
        "method": record.method,
        "url": record.url,
        "headers": record.headers,
        "body": record.body,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _environment_response(record: Environment, db: Session) -> dict[str, Any]:
    if not record.secrets_migrated:
        try:
            legacy_ciphertext = encrypt_environment_values(record.variables)
        except SecretStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        record.secret_variables = {**record.secret_variables, **legacy_ciphertext}
        record.variables = {}
        record.secrets_migrated = True
        db.commit()
        db.refresh(record)
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "name": record.name,
        "base_url": record.base_url,
        "variables": record.variables,
        "secrets": {name: {"has_value": True} for name in record.secret_variables},
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.get("/saved-requests")
def list_saved_requests(
    project_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    return [
        _saved_response(record)
        for record in db.scalars(
            select(SavedRequest)
            .where(SavedRequest.project_id == project.id)
            .order_by(SavedRequest.collection_name, SavedRequest.name)
        )
    ]


@router.post("/saved-requests", status_code=status.HTTP_201_CREATED)
def create_saved_request(
    project_id: UUID,
    payload: SavedRequestInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = SavedRequest(project_id=project.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return _saved_response(record)


@router.put("/saved-requests/{request_id}")
def update_saved_request(
    project_id: UUID,
    request_id: UUID,
    payload: SavedRequestInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(SavedRequest).where(
            SavedRequest.id == request_id, SavedRequest.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Saved request not found.")
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return _saved_response(record)


@router.delete("/saved-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_request(
    project_id: UUID,
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    project = _project(db, project_id)
    record = db.scalar(
        select(SavedRequest).where(
            SavedRequest.id == request_id, SavedRequest.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Saved request not found.")
    db.delete(record)
    db.commit()


@router.get("/environments")
def list_environments(
    project_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    return [
        _environment_response(record, db)
        for record in db.scalars(
            select(Environment)
            .where(Environment.project_id == project.id)
            .order_by(Environment.name)
        )
    ]


@router.post("/environments", status_code=status.HTTP_201_CREATED)
def create_environment(
    project_id: UUID,
    payload: EnvironmentInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    if set(payload.variables) & set(payload.secrets):
        raise HTTPException(status_code=422, detail="A variable cannot be both public and secret.")
    try:
        encrypted_secrets = encrypt_environment_values(payload.secrets)
    except SecretStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record = Environment(
        project_id=project.id,
        name=payload.name,
        base_url=payload.base_url,
        variables=payload.variables,
        secret_variables=encrypted_secrets,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _environment_response(record, db)


@router.put("/environments/{environment_id}")
def update_environment(
    project_id: UUID,
    environment_id: UUID,
    payload: EnvironmentInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(Environment).where(
            Environment.id == environment_id, Environment.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Environment not found.")
    _environment_response(record, db)
    if set(payload.variables) & set(payload.secrets):
        raise HTTPException(status_code=422, detail="A variable cannot be both public and secret.")
    if set(payload.secrets) & set(payload.remove_secrets):
        raise HTTPException(
            status_code=422,
            detail="A secret cannot be replaced and removed together.",
        )
    try:
        encrypted_secrets = encrypt_environment_values(payload.secrets)
    except SecretStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record.name = payload.name
    record.base_url = payload.base_url
    record.variables = payload.variables
    record.secret_variables = {
        **{
            key: value
            for key, value in record.secret_variables.items()
            if key not in payload.remove_secrets
        },
        **encrypted_secrets,
    }
    db.commit()
    db.refresh(record)
    return _environment_response(record, db)


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(
    project_id: UUID,
    environment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    project = _project(db, project_id)
    record = db.scalar(
        select(Environment).where(
            Environment.id == environment_id, Environment.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Environment not found.")
    db.delete(record)
    db.commit()
