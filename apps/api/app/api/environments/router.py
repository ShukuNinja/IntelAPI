from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth.dependencies import get_current_user
from app.api.environments.schemas import (
    VARIABLE_KEY_PATTERN,
    EnvironmentCreate,
    EnvironmentListRead,
    EnvironmentRead,
    EnvironmentUpdate,
    EnvironmentVariableRead,
    EnvironmentVariableWrite,
)
from app.api.projects.router import get_owned_project
from app.core.encryption import encrypt_secret
from app.db.session import get_db
from app.models.environment import Environment
from app.models.environment_variable import EnvironmentVariable
from app.models.project import Project
from app.models.user import User

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "NOT_FOUND", "message": "Resource not found."},
    )


def _environment_not_found(db: Session, environment_id: UUID, owner_user_id: UUID) -> Environment:
    environment = db.scalar(
        select(Environment)
        .join(Project, Environment.project_id == Project.id)
        .options(selectinload(Environment.variables))
        .where(
            Environment.id == environment_id,
            Project.owner_user_id == owner_user_id,
            Project.deleted_at.is_(None),
        )
    )
    if environment is None:
        raise _not_found()
    return environment


def _to_environment_read(environment: Environment) -> EnvironmentRead:
    variables = []
    for variable in environment.variables:
        variables.append(
            EnvironmentVariableRead(
                key=variable.key,
                value=None if variable.is_secret else variable.value_plain,
                is_secret=variable.is_secret,
                created_at=variable.created_at,
                updated_at=variable.updated_at,
            )
        )

    return EnvironmentRead(
        id=environment.id,
        project_id=environment.project_id,
        name=environment.name,
        base_url=environment.base_url,
        created_at=environment.created_at,
        updated_at=environment.updated_at,
        variables=variables,
    )


def _commit_environment_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONFLICT",
                "message": "An environment with that name or variable key already exists.",
            },
        ) from exc


@router.get("/projects/{project_id}/environments", response_model=EnvironmentListRead)
def list_environments(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EnvironmentListRead:
    get_owned_project(db, project_id, current_user.id)

    total = (
        db.scalar(
            select(func.count())
            .select_from(Environment)
            .where(Environment.project_id == project_id)
        )
        or 0
    )

    environments = db.scalars(
        select(Environment)
        .options(selectinload(Environment.variables))
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at.desc(), Environment.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return EnvironmentListRead(
        items=[_to_environment_read(item) for item in environments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/projects/{project_id}/environments",
    response_model=EnvironmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_environment(
    project_id: UUID,
    payload: EnvironmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> EnvironmentRead:
    get_owned_project(db, project_id, current_user.id)

    environment = Environment(
        project_id=project_id,
        name=payload.name,
        base_url=payload.base_url,
    )
    db.add(environment)
    _commit_environment_change(db)
    db.refresh(environment)

    return _to_environment_read(environment)


@router.get("/environments/{environment_id}", response_model=EnvironmentRead)
def get_environment(
    environment_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> EnvironmentRead:
    environment = _environment_not_found(db, environment_id, current_user.id)
    return _to_environment_read(environment)


@router.patch("/environments/{environment_id}", response_model=EnvironmentRead)
def update_environment(
    environment_id: UUID,
    payload: EnvironmentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> EnvironmentRead:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "At least one field is required."},
        )

    environment = _environment_not_found(db, environment_id, current_user.id)

    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": "Name cannot be null."},
            )
        environment.name = payload.name

    if "base_url" in payload.model_fields_set:
        environment.base_url = payload.base_url

    _commit_environment_change(db)
    db.refresh(environment)

    return get_environment(environment_id, db, current_user)


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(
    environment_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    environment = _environment_not_found(db, environment_id, current_user.id)
    db.delete(environment)
    db.commit()


@router.put(
    "/environments/{environment_id}/variables/{key}",
    response_model=EnvironmentVariableRead,
)
def upsert_environment_variable(
    environment_id: UUID,
    key: str,
    payload: EnvironmentVariableWrite,
    db: DbSession,
    current_user: CurrentUser,
) -> EnvironmentVariableRead:
    if not VARIABLE_KEY_PATTERN.fullmatch(key):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": (
                    "Variable keys must start with a letter or underscore and "
                    "contain only letters, digits, and underscores."
                ),
            },
        )

    environment = _environment_not_found(db, environment_id, current_user.id)

    variable = db.scalar(
        select(EnvironmentVariable).where(
            EnvironmentVariable.environment_id == environment.id,
            EnvironmentVariable.key == key,
        )
    )

    if variable is None:
        variable = EnvironmentVariable(
            environment_id=environment.id,
            key=key,
            is_secret=payload.is_secret,
        )
        db.add(variable)

    variable.is_secret = payload.is_secret
    variable.value_ciphertext = encrypt_secret(payload.value) if payload.is_secret else None
    variable.value_plain = None if payload.is_secret else payload.value

    _commit_environment_change(db)
    db.refresh(variable)

    return EnvironmentVariableRead(
        key=variable.key,
        value=None if variable.is_secret else variable.value_plain,
        is_secret=variable.is_secret,
        created_at=variable.created_at,
        updated_at=variable.updated_at,
    )
