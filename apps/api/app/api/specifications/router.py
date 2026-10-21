"""Persisted OpenAPI specifications and non-persisting candidate previews."""

from dataclasses import asdict
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.executions.schemas import ExecutionRequest
from app.api.executions.service import ExecutionError, execute_request
from app.api.projects.router import get_owned_project
from app.api.specifications.schemas import (
    CandidatePreviewRead,
    CandidatePreviewRequest,
    CandidateRead,
    KnowledgeFactRead,
    OperationListRead,
    OperationRead,
    SpecificationDetailRead,
    SpecificationImport,
    SpecificationListRead,
    SpecificationRead,
)
from app.db.session import get_db
from app.integrations.llm import create_llm_provider
from app.models.api_specification import APIOperation, APISpecification, KnowledgeFact
from app.models.project import Project
from app.models.user import User
from app.modules.api_understanding import (
    NormalizedOperation,
    normalize_operations,
    normalized_operation_from_document,
    parse_openapi_document,
)
from app.modules.api_understanding.errors import OpenAPIError
from app.modules.knowledge.extractor import extract_operation_facts
from app.modules.test_generation import (
    CandidatePreviewError,
    generate_candidates,
    preview_candidates,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Resource not found."}
    )


def _spec_read(db: Session, specification: APISpecification) -> SpecificationRead:
    count = (
        db.scalar(
            select(func.count())
            .select_from(APIOperation)
            .where(APIOperation.specification_id == specification.id)
        )
        or 0
    )
    return SpecificationRead(
        id=specification.id,
        project_id=specification.project_id,
        created_by_user_id=specification.created_by_user_id,
        name=specification.name,
        source_kind=specification.source_kind,
        source_url=specification.source_url,
        content_sha256=specification.content_sha256,
        spec_version=specification.spec_version,
        openapi_version=specification.openapi_version,
        created_at=specification.created_at,
        operation_count=count,
    )


def _owned_spec(db: Session, spec_id: UUID, user_id: UUID) -> APISpecification:
    result = db.scalar(
        select(APISpecification)
        .join(Project, Project.id == APISpecification.project_id)
        .where(
            APISpecification.id == spec_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if result is None:
        raise _not_found()
    return result


def _owned_operation(db: Session, operation_id: UUID, user_id: UUID) -> APIOperation:
    result = db.scalar(
        select(APIOperation)
        .join(APISpecification)
        .join(Project, Project.id == APISpecification.project_id)
        .where(
            APIOperation.id == operation_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if result is None:
        raise _not_found()
    return result


@router.get("/projects/{project_id}/specifications", response_model=SpecificationListRead)
def list_specifications(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SpecificationListRead:
    get_owned_project(db, project_id, current_user.id)
    filters = APISpecification.project_id == project_id
    total = db.scalar(select(func.count()).select_from(APISpecification).where(filters)) or 0
    specs = db.scalars(
        select(APISpecification)
        .where(filters)
        .order_by(APISpecification.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return SpecificationListRead(
        items=[_spec_read(db, item) for item in specs],
        pagination={"limit": limit, "offset": offset, "total": total},
    )


@router.post(
    "/projects/{project_id}/specifications/import",
    response_model=SpecificationRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_specification(
    project_id: UUID, payload: SpecificationImport, db: DbSession, current_user: CurrentUser
) -> SpecificationRead:
    project = get_owned_project(db, project_id, current_user.id)
    source_kind = "url" if payload.url is not None else "file"
    source_url = str(payload.url) if payload.url is not None else None
    if source_url:
        try:
            response = await execute_request(
                ExecutionRequest(
                    url=payload.url,
                    headers={"Accept": "application/json, application/yaml, text/yaml, text/plain"},
                )
            )
        except ExecutionError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "SPEC_FETCH_FAILED", "message": str(exc)}
            ) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "SPEC_FETCH_FAILED",
                    "message": f"Specification URL returned HTTP {response.status_code}.",
                },
            )
        content = response.body
    else:
        content = payload.content
    if content is None:
        raise HTTPException(status_code=422, detail="Provide specification content or URL.")
    try:
        document = parse_openapi_document(content)
        operations = normalize_operations(document)
    except (OpenAPIError, RecursionError) as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OPENAPI", "message": str(exc)}
        ) from exc

    digest = sha256(content.encode("utf-8")).hexdigest()
    existing = db.scalar(
        select(APISpecification).where(
            APISpecification.project_id == project_id, APISpecification.content_sha256 == digest
        )
    )
    if existing is not None:
        return _spec_read(db, existing)

    specification = APISpecification(
        project_id=project.id,
        created_by_user_id=current_user.id,
        name=payload.name or document["info"]["title"],
        source_kind=source_kind,
        source_url=source_url,
        spec_document=document,
        content_sha256=digest,
        openapi_version=document.get("openapi"),
    )
    db.add(specification)
    db.flush()
    for operation in operations:
        operation_document = asdict(operation)
        operation_document["source_ref"] = asdict(operation.source_ref)
        row = APIOperation(
            specification_id=specification.id,
            operation_key=operation.operation_key,
            method=operation.method,
            path_template=operation.path,
            summary=operation.summary,
            operation_document=operation_document,
        )
        db.add(row)
        db.flush()
        for fact in extract_operation_facts(operation):
            db.add(
                KnowledgeFact(
                    project_id=project_id,
                    specification_id=specification.id,
                    operation_id=row.id,
                    fact_type=fact.fact_type,
                    subject=operation.operation_key,
                    fact_value=fact.value,
                    provenance=fact.provenance.value,
                    source_ref=asdict(fact.source_ref),
                )
            )
    db.commit()
    db.refresh(specification)
    return _spec_read(db, specification)


@router.get("/specifications/{specification_id}", response_model=SpecificationDetailRead)
def get_specification(
    specification_id: UUID, db: DbSession, current_user: CurrentUser
) -> SpecificationDetailRead:
    item = _owned_spec(db, specification_id, current_user.id)
    return SpecificationDetailRead(
        **_spec_read(db, item).model_dump(), spec_document=item.spec_document
    )


@router.get("/specifications/{specification_id}/operations", response_model=OperationListRead)
def list_operations(
    specification_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OperationListRead:
    _owned_spec(db, specification_id, current_user.id)
    filters = APIOperation.specification_id == specification_id
    total = db.scalar(select(func.count()).select_from(APIOperation).where(filters)) or 0
    rows = db.scalars(
        select(APIOperation)
        .where(filters)
        .order_by(APIOperation.operation_key)
        .limit(limit)
        .offset(offset)
    ).all()
    return OperationListRead(
        items=[OperationRead.model_validate(row) for row in rows],
        pagination={"limit": limit, "offset": offset, "total": total},
    )


@router.get("/operations/{operation_id}", response_model=OperationRead)
def get_operation(operation_id: UUID, db: DbSession, current_user: CurrentUser) -> OperationRead:
    return OperationRead.model_validate(_owned_operation(db, operation_id, current_user.id))


@router.get("/operations/{operation_id}/knowledge-facts", response_model=list[KnowledgeFactRead])
def list_knowledge_facts(
    operation_id: UUID, db: DbSession, current_user: CurrentUser
) -> list[KnowledgeFactRead]:
    operation = _owned_operation(db, operation_id, current_user.id)
    rows = db.scalars(
        select(KnowledgeFact)
        .where(KnowledgeFact.operation_id == operation.id)
        .order_by(KnowledgeFact.created_at, KnowledgeFact.id)
    ).all()
    return [KnowledgeFactRead.model_validate(row) for row in rows]


def _normalized_operation(row: APIOperation) -> NormalizedOperation:
    return normalized_operation_from_document(row.operation_document)


@router.post("/operations/{operation_id}/candidates/preview", response_model=CandidatePreviewRead)
def preview_operation_candidates(
    operation_id: UUID, payload: CandidatePreviewRequest, db: DbSession, current_user: CurrentUser
) -> CandidatePreviewRead:
    operation = _normalized_operation(_owned_operation(db, operation_id, current_user.id))
    if payload.llm:
        try:
            result = preview_candidates(
                (operation,),
                categories=tuple(payload.categories) if payload.categories is not None else None,
                limit=payload.limit,
                provider=create_llm_provider(),
            )
        except CandidatePreviewError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        candidates, llm_status, llm_error = (
            result.candidates,
            result.llm_status.value,
            result.llm_error,
        )
    else:
        candidates = generate_candidates((operation,))
        if payload.categories is not None:
            if not payload.categories:
                raise HTTPException(
                    status_code=422,
                    detail="categories must contain at least one category when provided.",
                )
            categories = set(payload.categories)
            candidates = tuple(c for c in candidates if c.category in categories)
        candidates, llm_status, llm_error = candidates[: payload.limit], "disabled", None
    return CandidatePreviewRead(
        items=[
            CandidateRead(
                candidate_id=c.candidate_id,
                operation_key=c.operation_key,
                category=c.category,
                title=c.title,
                method=c.method,
                path=c.path,
                parameters=c.parameters,
                body=c.body,
                rationale=c.rationale,
            )
            for c in candidates
        ],
        llm_status=llm_status,
        llm_error=llm_error,
    )
