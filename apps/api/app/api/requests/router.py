from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.projects.router import get_owned_project
from app.api.requests.schemas import (
    PaginationRead,
    SavedRequestCreate,
    SavedRequestListRead,
    SavedRequestRead,
    SavedRequestUpdate,
)
from app.db.session import get_db
from app.models.collection import Collection
from app.models.environment import Environment
from app.models.project import Project
from app.models.saved_request import SavedRequest
from app.models.user import User

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "NOT_FOUND",
            "message": "Saved request not found.",
        },
    )


def _validate_references(
    db: Session,
    project_id: UUID,
    collection_id: UUID | None,
    environment_id: UUID | None,
) -> None:
    if collection_id is not None:
        collection_project_id = db.scalar(
            select(Collection.project_id).where(Collection.id == collection_id)
        )
        if collection_project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "The collection must belong to the same project.",
                },
            )

    if environment_id is not None:
        environment_project_id = db.scalar(
            select(Environment.project_id).where(Environment.id == environment_id)
        )
        if environment_project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "The environment must belong to the same project.",
                },
            )


def _get_owned_request(
    db: Session,
    request_id: UUID,
    owner_user_id: UUID,
) -> SavedRequest:
    saved_request = db.scalar(
        select(SavedRequest)
        .join(Project, SavedRequest.project_id == Project.id)
        .where(
            SavedRequest.id == request_id,
            Project.owner_user_id == owner_user_id,
            Project.deleted_at.is_(None),
        )
    )

    if saved_request is None:
        raise _not_found()

    return saved_request


def _validate_body_type(body_type: str, body: object) -> None:
    if body_type == "none" and body is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "A request with body_type 'none' cannot have a body.",
            },
        )


@router.get(
    "/projects/{project_id}/requests",
    response_model=SavedRequestListRead,
)
def list_saved_requests(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    collection_id: UUID | None = None,
) -> SavedRequestListRead:
    get_owned_project(db, project_id, current_user.id)

    filters = [SavedRequest.project_id == project_id]
    if collection_id is not None:
        filters.append(SavedRequest.collection_id == collection_id)

    total = db.scalar(select(func.count()).select_from(SavedRequest).where(*filters)) or 0

    requests = db.scalars(
        select(SavedRequest)
        .where(*filters)
        .order_by(SavedRequest.updated_at.desc(), SavedRequest.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return SavedRequestListRead(
        items=[SavedRequestRead.model_validate(item) for item in requests],
        pagination=PaginationRead(limit=limit, offset=offset, total=total),
    )


@router.post(
    "/projects/{project_id}/requests",
    response_model=SavedRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_saved_request(
    project_id: UUID,
    payload: SavedRequestCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SavedRequestRead:
    get_owned_project(db, project_id, current_user.id)

    _validate_references(
        db,
        project_id,
        payload.collection_id,
        payload.environment_id,
    )
    _validate_body_type(payload.body_type, payload.body)

    saved_request = SavedRequest(
        project_id=project_id,
        name=payload.name,
        method=payload.method,
        url_template=payload.url_template,
        collection_id=payload.collection_id,
        environment_id=payload.environment_id,
        headers=payload.headers,
        query_params=payload.query_params,
        body=payload.body,
        body_type=payload.body_type,
    )

    db.add(saved_request)
    db.commit()
    db.refresh(saved_request)

    return SavedRequestRead.model_validate(saved_request)


@router.get(
    "/requests/{request_id}",
    response_model=SavedRequestRead,
)
def get_saved_request(
    request_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> SavedRequestRead:
    saved_request = _get_owned_request(db, request_id, current_user.id)
    return SavedRequestRead.model_validate(saved_request)


@router.patch(
    "/requests/{request_id}",
    response_model=SavedRequestRead,
)
def update_saved_request(
    request_id: UUID,
    payload: SavedRequestUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> SavedRequestRead:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "At least one saved-request field must be supplied.",
            },
        )

    saved_request = _get_owned_request(db, request_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)

    for field in ("name", "method", "url_template", "headers", "query_params", "body_type"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"{field} cannot be null.",
                },
            )

    new_collection_id = changes.get("collection_id", saved_request.collection_id)
    new_environment_id = changes.get("environment_id", saved_request.environment_id)
    new_body_type = changes.get("body_type", saved_request.body_type)
    new_body = changes.get("body", saved_request.body)

    _validate_references(
        db,
        saved_request.project_id,
        new_collection_id,
        new_environment_id,
    )
    _validate_body_type(new_body_type, new_body)

    for field, value in changes.items():
        setattr(saved_request, field, value)

    db.commit()
    db.refresh(saved_request)

    return SavedRequestRead.model_validate(saved_request)


@router.delete(
    "/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_saved_request(
    request_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    saved_request = _get_owned_request(db, request_id, current_user.id)
    db.delete(saved_request)
    db.commit()
