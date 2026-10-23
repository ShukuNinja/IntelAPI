import json
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ApiSpecification,
    CampaignEventRecord,
    CampaignJobRecord,
    CampaignRecord,
    Environment,
    GenerationReportRecord,
    Project,
    TestCaseRecord,
    User,
)
from app.modules.campaigns.service import (
    append_event,
    campaign_event_read,
    campaign_report,
)
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}/campaigns", tags=["campaigns"])
TERMINAL_STATES = {"completed", "failed", "cancelled"}


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    generation_report_id: UUID
    base_url: AnyHttpUrl
    environment_id: UUID | None = None
    candidate_ids: list[str] | None = Field(default=None, max_length=100)
    baseline_by_operation: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=100)
    max_executions: int = Field(default=10, ge=1, le=50)
    max_iterations: int = Field(default=10, ge=1, le=50)
    max_duration_seconds: int = Field(default=120, ge=1, le=600)
    confirm_unsafe: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Campaign name cannot be blank.")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        parsed = urlsplit(str(value))
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "Campaign base URLs cannot contain credentials, query values, or fragments."
            )
        return value

    @field_validator("baseline_by_operation")
    @classmethod
    def bound_baseline_size(cls, value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 2_000_000:
            raise ValueError("Campaign baseline values cannot exceed 2 MB.")
        return value


def _project(db: Session, project_id: UUID) -> tuple[Project, User]:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503,
            detail="Campaigns are disabled until application authentication is configured.",
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
    if project is None or user is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project, user


def _campaign(db: Session, project: Project, campaign_id: UUID) -> CampaignRecord:
    campaign = db.scalar(
        select(CampaignRecord).where(
            CampaignRecord.id == campaign_id,
            CampaignRecord.project_id == project.id,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


def _campaign_read(db: Session, campaign: CampaignRecord) -> dict[str, Any]:
    report = campaign_report(db, campaign)
    return {**report["campaign"], "progress": report["summary"]}


@router.get("")
def list_campaigns(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    project, _ = _project(db, project_id)
    return [
        _campaign_read(db, campaign)
        for campaign in db.scalars(
            select(CampaignRecord)
            .where(CampaignRecord.project_id == project.id)
            .order_by(CampaignRecord.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
    ]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_campaign(
    project_id: UUID,
    payload: CampaignCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project, user = _project(db, project_id)
    report = db.scalar(
        select(GenerationReportRecord).where(
            GenerationReportRecord.id == payload.generation_report_id,
            GenerationReportRecord.project_id == project.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Generation report not found.")
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == report.specification_id,
            ApiSpecification.project_id == project.id,
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    operation_by_id = {
        item.get("id"): item for item in specification.normalized_operations if item.get("id")
    }
    if set(payload.baseline_by_operation) - set(operation_by_id):
        raise HTTPException(
            status_code=422, detail="Baseline values include an unknown operation ID."
        )
    if payload.environment_id is not None:
        environment = db.scalar(
            select(Environment).where(
                Environment.id == payload.environment_id,
                Environment.project_id == project.id,
            )
        )
        if environment is None:
            raise HTTPException(status_code=404, detail="Environment not found in this project.")
    selected_ids = set(payload.candidate_ids or [])
    candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    available_ids: set[str] = set()
    for endpoint in report.report.get("endpoints", []):
        summary = endpoint.get("operation", {})
        operation = operation_by_id.get(summary.get("id"))
        if operation is None:
            continue
        for candidate in endpoint.get("candidates", []):
            candidate_id = candidate.get("id")
            if not isinstance(candidate_id, str):
                continue
            available_ids.add(candidate_id)
            if not selected_ids or candidate_id in selected_ids:
                candidates.append((candidate_id, operation, candidate))
    if selected_ids - available_ids:
        raise HTTPException(
            status_code=422, detail="One or more candidate IDs are not in this report."
        )
    candidates = candidates[: payload.max_iterations]
    if not candidates:
        raise HTTPException(status_code=422, detail="Select at least one generated candidate.")
    base_url = str(payload.base_url).rstrip("/")
    campaign = CampaignRecord(
        project_id=project.id,
        created_by_user_id=user.id,
        specification_id=specification.id,
        name=payload.name,
        state="queued",
        configuration={
            "generation_report_id": str(report.id),
            "base_url": base_url,
            "environment_id": str(payload.environment_id) if payload.environment_id else None,
            "baseline_by_operation": payload.baseline_by_operation,
            "confirm_unsafe": payload.confirm_unsafe,
        },
        budget_max_executions=payload.max_executions,
        budget_max_iterations=payload.max_iterations,
        budget_max_duration_seconds=payload.max_duration_seconds,
    )
    db.add(campaign)
    db.flush()
    for candidate_id, operation, candidate in candidates:
        operation_snapshot = {
            "id": operation.get("id"),
            "method": operation.get("method"),
            "path": operation.get("path"),
            "parameters": [
                {"name": item.get("name"), "in": item.get("in")}
                for item in operation.get("parameters", [])
                if isinstance(item, dict)
            ],
        }
        candidate_snapshot = {
            "id": candidate_id,
            "kind": candidate.get("kind"),
            "reason": candidate.get("reason"),
            "mutation": candidate.get("mutation", {}),
        }
        db.add(
            TestCaseRecord(
                project_id=project.id,
                campaign_id=campaign.id,
                operation_id=operation.get("id"),
                candidate_key=candidate_id,
                category="boundary",
                title=(candidate.get("reason") or candidate.get("kind") or candidate_id)[:200],
                description=candidate.get("reason"),
                request_override={"operation": operation_snapshot, "candidate": candidate_snapshot},
                expected_behavior=None,
                generation_provenance="INFERRED",
                state="queued",
            )
        )
    db.add(CampaignJobRecord(campaign_id=campaign.id, state="queued", attempt_count=0))
    append_event(
        db,
        campaign.id,
        "campaign_queued",
        {"test_count": len(candidates), "generation_report_id": str(report.id)},
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_read(db, campaign)


@router.get("/{campaign_id}")
def get_campaign(
    project_id: UUID,
    campaign_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project, _ = _project(db, project_id)
    return _campaign_read(db, _campaign(db, project, campaign_id))


@router.get("/{campaign_id}/report")
def get_campaign_report(
    project_id: UUID,
    campaign_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project, _ = _project(db, project_id)
    return campaign_report(db, _campaign(db, project, campaign_id))


@router.get("/{campaign_id}/events")
def list_campaign_events(
    project_id: UUID,
    campaign_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    after: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    project, _ = _project(db, project_id)
    campaign = _campaign(db, project, campaign_id)
    return [
        campaign_event_read(event)
        for event in db.scalars(
            select(CampaignEventRecord)
            .where(
                CampaignEventRecord.campaign_id == campaign.id,
                CampaignEventRecord.sequence_number > max(0, after),
            )
            .order_by(CampaignEventRecord.sequence_number)
            .limit(max(1, min(limit, 500)))
        )
    ]


@router.post("/{campaign_id}/cancel")
def cancel_campaign(
    project_id: UUID,
    campaign_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project, _ = _project(db, project_id)
    campaign = _campaign(db, project, campaign_id)
    if campaign.state in TERMINAL_STATES:
        return _campaign_read(db, campaign)
    now = datetime.now(UTC)
    campaign.cancel_requested_at = campaign.cancel_requested_at or now
    job = db.scalar(select(CampaignJobRecord).where(CampaignJobRecord.campaign_id == campaign.id))
    if campaign.state == "queued":
        campaign.state = "cancelled"
        campaign.completed_at = now
        if job:
            job.state = "cancelled"
        for case in db.scalars(
            select(TestCaseRecord).where(
                TestCaseRecord.campaign_id == campaign.id,
                TestCaseRecord.state == "queued",
            )
        ):
            case.state = "skipped"
            case.result = {"outcome": "cancelled_before_execution"}
        append_event(db, campaign.id, "campaign_cancelled", {"before_start": True})
    else:
        append_event(db, campaign.id, "cancellation_requested", {})
    db.commit()
    return _campaign_read(db, campaign)
