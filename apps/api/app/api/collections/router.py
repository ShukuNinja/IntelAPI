from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.collections.schemas import (
    CollectionCreate,
    CollectionListRead,
    CollectionRead,
    CollectionUpdate,
    PaginationRead,
)
from app.api.projects.router import get_owned_project
from app.db.session import get_db
from app.models.collection import Collection
from app.models.project import Project
from app.models.user import User

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "NOT_FOUND",
            "message": "Collection not found.",
        },
    )


def _conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "CONFLICT",
            "message": ("A collection with that name already exists in this project."),
        },
    )


def _get_owned_collection(
    db: Session,
    collection_id: UUID,
    owner_user_id: UUID,
) -> Collection:
    collection = db.scalar(
        select(Collection)
        .join(Project, Collection.project_id == Project.id)
        .where(
            Collection.id == collection_id,
            Project.owner_user_id == owner_user_id,
            Project.deleted_at.is_(None),
        )
    )

    if collection is None:
        raise _not_found()

    return collection


@router.get(
    "/projects/{project_id}/collections",
    response_model=CollectionListRead,
)
def list_collections(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CollectionListRead:
    get_owned_project(db, project_id, current_user.id)

    total = (
        db.scalar(
            select(func.count()).select_from(Collection).where(Collection.project_id == project_id)
        )
        or 0
    )

    collections = db.scalars(
        select(Collection)
        .where(Collection.project_id == project_id)
        .order_by(Collection.created_at.desc(), Collection.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return CollectionListRead(
        items=[CollectionRead.model_validate(item) for item in collections],
        pagination=PaginationRead(
            limit=limit,
            offset=offset,
            total=total,
        ),
    )


@router.post(
    "/projects/{project_id}/collections",
    response_model=CollectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_collection(
    project_id: UUID,
    payload: CollectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CollectionRead:
    get_owned_project(db, project_id, current_user.id)

    collection = Collection(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )

    try:
        with db.begin_nested():
            db.add(collection)
            db.flush()
    except IntegrityError as exc:
        raise _conflict() from exc

    db.commit()
    db.refresh(collection)

    return CollectionRead.model_validate(collection)


@router.get(
    "/collections/{collection_id}",
    response_model=CollectionRead,
)
def get_collection(
    collection_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CollectionRead:
    collection = _get_owned_collection(
        db,
        collection_id,
        current_user.id,
    )
    return CollectionRead.model_validate(collection)


@router.patch(
    "/collections/{collection_id}",
    response_model=CollectionRead,
)
def update_collection(
    collection_id: UUID,
    payload: CollectionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CollectionRead:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "At least one collection field must be supplied.",
            },
        )

    if "name" in payload.model_fields_set and payload.name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Collection name cannot be null.",
            },
        )

    collection = _get_owned_collection(
        db,
        collection_id,
        current_user.id,
    )

    if "name" in payload.model_fields_set:
        # The null case is rejected above.
        assert payload.name is not None
        collection.name = payload.name

    if "description" in payload.model_fields_set:
        collection.description = payload.description

    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise _conflict() from exc

    db.commit()
    db.refresh(collection)

    return CollectionRead.model_validate(collection)


@router.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_collection(
    collection_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    collection = _get_owned_collection(
        db,
        collection_id,
        current_user.id,
    )

    db.delete(collection)
    db.commit()
