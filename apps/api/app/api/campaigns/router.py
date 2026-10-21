"""Authenticated API for durable, bounded test campaigns."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth.dependencies import get_current_user
from app.api.campaigns.schemas import (
    CampaignCreate,
    CampaignEventRead,
    CampaignListRead,
    CampaignRead,
    CampaignReportRead,
    TestCaseRead,
)
from app.api.executions.persisted_schemas import ExecutionListRead, ExecutionRead
from app.db.session import get_db
from app.models.api_specification import APIOperation, APISpecification
from app.models.campaign import Campaign, CampaignEvent, CampaignJob, TestCase
from app.models.environment import Environment
from app.models.execution import Execution
from app.models.finding import Finding
from app.models.project import Project
from app.models.saved_request import SavedRequest
from app.models.user import User
from app.modules.api_understanding import NormalizedOperation, normalized_operation_from_document
from app.modules.assertion_analysis import analyze_operation
from app.modules.test_generation import CandidateCategory, generate_candidates

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Campaign not found."}
    )


def _owned_campaign(
    db: Session, campaign_id: UUID, user_id: UUID, *, lock: bool = False
) -> Campaign:
    query = (
        select(Campaign)
        .join(Project)
        .where(
            Campaign.id == campaign_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if lock:
        query = query.with_for_update()
    campaign = db.scalar(query)
    if campaign is None:
        raise _not_found()
    return campaign


def campaign_read(db: Session, row: Campaign) -> CampaignRead:
    tests = (
        db.scalar(select(func.count()).select_from(TestCase).where(TestCase.campaign_id == row.id))
        or 0
    )
    executions = (
        db.scalar(
            select(func.count()).select_from(Execution).where(Execution.campaign_id == row.id)
        )
        or 0
    )
    return CampaignRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        state=row.state,
        configuration=row.configuration,
        budget_max_executions=row.budget_max_executions,
        budget_max_iterations=row.budget_max_iterations,
        budget_max_duration_seconds=row.budget_max_duration_seconds,
        started_at=row.started_at,
        completed_at=row.completed_at,
        cancel_requested_at=row.cancel_requested_at,
        failure_code=row.failure_code,
        failure_summary=row.failure_summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
        test_count=tests,
        execution_count=executions,
    )


def append_event(
    db: Session, campaign_id: UUID, event_type: str, payload: dict[str, Any]
) -> CampaignEvent:
    last = (
        db.scalar(
            select(func.max(CampaignEvent.sequence_number)).where(
                CampaignEvent.campaign_id == campaign_id
            )
        )
        or 0
    )
    event = CampaignEvent(
        campaign_id=campaign_id, sequence_number=last + 1, event_type=event_type, payload=payload
    )
    db.add(event)
    return event


def _parameter_example(parameter: dict[str, Any]) -> Any:
    for key in ("example", "default"):
        if key in parameter:
            return parameter[key]
    schema = parameter.get("schema") or {}
    if isinstance(schema, dict):
        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            return enum[0]
        kind = schema.get("type")
        return {"integer": 1, "number": 1, "boolean": True, "array": [], "object": {}}.get(
            kind, "sample"
        )
    return "sample"


def _operation_case_values(operation: NormalizedOperation, candidate: Any) -> dict[str, Any] | None:
    values: dict[str, dict[str, Any]] = {"path": {}, "query": {}, "header": {}}
    omitted = candidate.title.startswith("Omit parameter:")
    omitted_name = candidate.title.removeprefix("Omit parameter:").strip() if omitted else None
    for parameter in operation.parameters:
        name, location = parameter.get("name"), parameter.get("in")
        if not isinstance(name, str) or location not in values:
            continue
        if location == "header" and name.lower() in {"authorization", "cookie", "host"}:
            continue
        if name == omitted_name:
            continue
        if parameter.get("required") or location == "path":
            values[location][name] = _parameter_example(parameter)
    if any(
        "{" + name + "}" in operation.path
        for name in _required_path_names(operation)
        if name not in values["path"]
    ):
        return None
    return values


def _required_path_names(operation: NormalizedOperation) -> set[str]:
    import re

    return set(re.findall(r"\{([^{}]+)\}", operation.path))


def _operation_assertions(operation: NormalizedOperation) -> dict[str, Any]:
    assertions = []
    success_status_codes = sorted(
        {
            int(response_key.split(":", maxsplit=1)[0])
            for response_key in operation.response_schemas
            if response_key.split(":", maxsplit=1)[0].isdigit()
            and 200 <= int(response_key.split(":", maxsplit=1)[0]) < 300
        }
    )
    for item in analyze_operation(operation):
        status_text = item.response_key.split(":", 1)[0]
        if not status_text.isdigit() or not 200 <= int(status_text) < 300:
            continue
        assertions.append(
            {
                "id": item.assertion_id,
                "type": item.assertion_type.value,
                "response_status_code": int(status_text),
                "target": item.target,
                "expected": item.expected,
                "source_ref": asdict(item.source_ref),
                "rationale": item.rationale,
            }
        )
    return {"success_status_codes": success_status_codes, "assertions": assertions}


@router.get("/projects/{project_id}/campaigns", response_model=CampaignListRead)
def list_campaigns(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CampaignListRead:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."}
        )
    total = (
        db.scalar(
            select(func.count()).select_from(Campaign).where(Campaign.project_id == project_id)
        )
        or 0
    )
    rows = db.scalars(
        select(Campaign)
        .where(Campaign.project_id == project_id)
        .order_by(Campaign.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return CampaignListRead(
        items=[campaign_read(db, row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.post(
    "/projects/{project_id}/campaigns",
    response_model=CampaignRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_campaign(
    project_id: UUID,
    payload: CampaignCreate,
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> CampaignRead:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."}
        )
    requests: list[SavedRequest] = []
    operation_rows: list[tuple[APIOperation, APISpecification]] = []
    if payload.saved_request_ids is not None:
        if len(set(payload.saved_request_ids)) != len(payload.saved_request_ids):
            raise HTTPException(status_code=422, detail="saved_request_ids must be unique.")
        requests = list(
            db.scalars(
                select(SavedRequest).where(
                    SavedRequest.project_id == project_id,
                    SavedRequest.id.in_(payload.saved_request_ids),
                )
            ).all()
        )
        if len(requests) != len(payload.saved_request_ids):
            raise HTTPException(
                status_code=422, detail="Every saved request must belong to this project."
            )
    else:
        assert payload.operation_ids is not None
        if len(set(payload.operation_ids)) != len(payload.operation_ids):
            raise HTTPException(status_code=422, detail="operation_ids must be unique.")
        operation_rows = list(
            db.execute(
                select(APIOperation, APISpecification)
                .join(APISpecification, APISpecification.id == APIOperation.specification_id)
                .where(
                    APIOperation.id.in_(payload.operation_ids),
                    APISpecification.project_id == project_id,
                )
            ).all()
        )
        if len(operation_rows) != len(payload.operation_ids):
            raise HTTPException(
                status_code=422, detail="Every operation must belong to this project."
            )
    if (
        payload.environment_id is not None
        and db.scalar(
            select(Environment.id).where(
                Environment.id == payload.environment_id, Environment.project_id == project_id
            )
        )
        is None
    ):
        raise HTTPException(status_code=422, detail="Environment must belong to this project.")
    if operation_rows and (
        db.scalar(
            select(Environment.id).where(
                Environment.id == payload.environment_id,
                Environment.project_id == project_id,
                Environment.base_url.is_not(None),
            )
        )
        is None
    ):
        raise HTTPException(
            status_code=422, detail="Environment must belong to the project and define a base URL."
        )
    cases: list[TestCase] = []
    if requests:
        for request in requests:
            cases.append(
                TestCase(
                    project_id=project_id,
                    candidate_key=f"saved-request:{request.id}",
                    category="baseline",
                    title=f"{request.method.upper()} {request.name}",
                    request_override={"saved_request_id": str(request.id)},
                    expected_behavior=None,
                    generation_provenance="DECLARED",
                )
            )
    else:
        for operation_row, specification in operation_rows:
            normalized = normalized_operation_from_document(operation_row.operation_document)
            document = specification.spec_document
            servers = document.get("servers", []) if isinstance(document, dict) else []
            server_path = ""
            if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
                server_path = urlsplit(servers[0]["url"]).path.rstrip("/")
            for candidate in generate_candidates((normalized,)):
                if candidate.category not in payload.categories:
                    continue
                parameters = _operation_case_values(normalized, candidate)
                if parameters is None:
                    continue
                has_body_schema = isinstance(normalized.request_body_schema, dict)
                if candidate.title == "Baseline request" and has_body_schema:
                    continue
                cases.append(
                    TestCase(
                        project_id=project_id,
                        operation_id=operation_row.id,
                        candidate_key=f"{operation_row.id}:{candidate.candidate_id}",
                        category=candidate.category.value,
                        title=candidate.title[:200],
                        description=candidate.rationale[:2000],
                        request_override={
                            "source": "openapi_candidate",
                            "candidate_id": candidate.candidate_id,
                            "operation_key": normalized.operation_key,
                            "method": candidate.method,
                            "path_template": candidate.path,
                            "server_path": server_path,
                            "parameters": parameters,
                            "body": candidate.body,
                        },
                        expected_behavior=_operation_assertions(normalized)
                        if candidate.category
                        in {CandidateCategory.POSITIVE, CandidateCategory.SCHEMA}
                        else None,
                        generation_provenance="EXTRACTED",
                    )
                )
    if not cases:
        raise HTTPException(
            status_code=422, detail="Selected inputs produced no executable test cases."
        )
    case_count = min(payload.max_iterations, payload.max_executions, len(cases))
    row = Campaign(
        project_id=project_id,
        created_by_user_id=current_user.id,
        name=payload.name.strip(),
        state="queued",
        configuration={
            "input_type": "saved_requests"
            if payload.saved_request_ids is not None
            else "openapi_operations",
            "saved_request_ids": [str(item) for item in payload.saved_request_ids]
            if payload.saved_request_ids is not None
            else [],
            "operation_ids": [str(item) for item in payload.operation_ids]
            if payload.operation_ids is not None
            else [],
            "environment_id": str(payload.environment_id) if payload.environment_id else None,
            "selected_categories": [item.value for item in payload.categories],
        },
        budget_max_executions=payload.max_executions,
        budget_max_iterations=payload.max_iterations,
        budget_max_duration_seconds=payload.max_duration_seconds,
    )
    db.add(row)
    db.flush()
    for case in cases[:case_count]:
        case.campaign_id = row.id
        db.add(case)
    db.add(CampaignJob(campaign_id=row.id, state="queued"))
    append_event(
        db,
        row.id,
        "campaign_queued",
        {
            "test_count": case_count,
            "budgets": {
                "max_executions": payload.max_executions,
                "max_iterations": payload.max_iterations,
                "max_duration_seconds": payload.max_duration_seconds,
            },
        },
    )
    db.commit()
    db.refresh(row)
    response.headers["Location"] = f"/api/v1/campaigns/{row.id}"
    return campaign_read(db, row)


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: UUID, db: DbSession, current_user: CurrentUser) -> CampaignRead:
    return campaign_read(db, _owned_campaign(db, campaign_id, current_user.id))


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignRead)
def cancel_campaign(campaign_id: UUID, db: DbSession, current_user: CurrentUser) -> CampaignRead:
    campaign = _owned_campaign(db, campaign_id, current_user.id, lock=True)
    if campaign.state not in {"completed", "failed", "cancelled"}:
        if campaign.cancel_requested_at is None:
            campaign.cancel_requested_at = datetime.now(UTC)
            append_event(db, campaign.id, "cancellation_requested", {})
            db.commit()
            db.refresh(campaign)
    return campaign_read(db, campaign)


@router.get("/campaigns/{campaign_id}/tests", response_model=list[TestCaseRead])
def list_campaign_tests(
    campaign_id: UUID, db: DbSession, current_user: CurrentUser
) -> list[TestCaseRead]:
    _owned_campaign(db, campaign_id, current_user.id)
    rows = db.scalars(
        select(TestCase)
        .where(TestCase.campaign_id == campaign_id)
        .order_by(TestCase.created_at, TestCase.id)
    ).all()
    return [TestCaseRead.model_validate(row) for row in rows]


@router.get("/campaigns/{campaign_id}/executions", response_model=ExecutionListRead)
def list_campaign_executions(
    campaign_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionListRead:
    _owned_campaign(db, campaign_id, current_user.id)
    filters = Execution.campaign_id == campaign_id
    total = db.scalar(select(func.count()).select_from(Execution).where(filters)) or 0
    rows = (
        db.scalars(
            select(Execution)
            .options(selectinload(Execution.evidence))
            .where(filters)
            .order_by(Execution.created_at.desc())
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


@router.get("/campaigns/{campaign_id}/events", response_model=list[CampaignEventRead])
def list_campaign_events(
    campaign_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CampaignEventRead]:
    _owned_campaign(db, campaign_id, current_user.id)
    rows = db.scalars(
        select(CampaignEvent)
        .where(
            CampaignEvent.campaign_id == campaign_id, CampaignEvent.sequence_number > after_sequence
        )
        .order_by(CampaignEvent.sequence_number)
        .limit(limit)
    ).all()
    return [CampaignEventRead.model_validate(row) for row in rows]


@router.get("/campaigns/{campaign_id}/report", response_model=CampaignReportRead)
def get_campaign_report(
    campaign_id: UUID, db: DbSession, current_user: CurrentUser
) -> CampaignReportRead:
    campaign = _owned_campaign(db, campaign_id, current_user.id)
    test_total = (
        db.scalar(
            select(func.count()).select_from(TestCase).where(TestCase.campaign_id == campaign_id)
        )
        or 0
    )
    execution_rows = db.scalars(select(Execution).where(Execution.campaign_id == campaign_id)).all()
    finding_total = (
        db.scalar(
            select(func.count()).select_from(Finding).where(Finding.campaign_id == campaign_id)
        )
        or 0
    )
    events = db.scalars(
        select(CampaignEvent)
        .where(CampaignEvent.campaign_id == campaign_id)
        .order_by(CampaignEvent.sequence_number)
    ).all()
    tests_executed = len(execution_rows)
    return CampaignReportRead(
        campaign=campaign_read(db, campaign),
        tests={
            "total": test_total,
            "executed": tests_executed,
            "pending": max(0, test_total - tests_executed),
        },
        executions={
            "total": tests_executed,
            "completed": sum(item.status == "completed" for item in execution_rows),
            "failed": sum(item.status == "failed" for item in execution_rows),
        },
        findings={"total": finding_total},
        events=[CampaignEventRead.model_validate(item) for item in events],
    )
