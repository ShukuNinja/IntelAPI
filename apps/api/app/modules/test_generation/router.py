import csv
import io
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import ApiSpecification, GenerationReportRecord, Project, User
from app.modules.api_understanding.service import generate_generation_report
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}", tags=["test-generation"])


class GenerateReportInput(BaseModel):
    per_operation_limit: int = Field(default=20, ge=1, le=20)


def _project(db: Session, project_id: UUID) -> Project:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503, detail="Local single-user reports are disabled in production."
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


def _report_response(record: GenerationReportRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "specification_id": str(record.specification_id),
        "created_at": record.created_at.isoformat(),
        **record.report,
    }


@router.post(
    "/specifications/{specification_id}/generation-reports",
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    project_id: UUID,
    specification_id: UUID,
    payload: GenerateReportInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id,
            ApiSpecification.project_id == project.id,
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    try:
        report = generate_generation_report(
            specification.normalized_operations,
            per_operation_limit=payload.per_operation_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["specification"] = {
        "id": str(specification.id),
        "title": specification.title,
        "version": specification.spec_version,
        "content_hash": specification.content_hash,
        "source_format": specification.source_format,
    }
    record = GenerationReportRecord(
        project_id=project.id,
        specification_id=specification.id,
        policy_version=report["policy_version"],
        report=report,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _report_response(record)


@router.get("/generation-reports")
def list_reports(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    return [
        {
            "id": str(record.id),
            "specification_id": str(record.specification_id),
            "policy_version": record.policy_version,
            "candidate_count": record.report["summary"]["candidate_count"],
            "operation_count": record.report["summary"]["operation_count"],
            "created_at": record.created_at.isoformat(),
        }
        for record in db.scalars(
            select(GenerationReportRecord)
            .where(GenerationReportRecord.project_id == project.id)
            .order_by(GenerationReportRecord.created_at.desc())
            .limit(limit)
        )
    ]


@router.get("/generation-reports/{report_id}")
def get_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(GenerationReportRecord).where(
            GenerationReportRecord.id == report_id,
            GenerationReportRecord.project_id == project.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Generation report not found.")
    return _report_response(record)


@router.get("/generation-reports/{report_id}/export")
def export_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown", "csv"] = Query(),
) -> Response:
    report_record = get_report(project_id, report_id, db)
    filename = f"generation-report-{report_id}"
    if format == "json":
        body = json.dumps(report_record, ensure_ascii=False, indent=2)
        media_type = "application/json"
        suffix = "json"
    elif format == "markdown":
        body = _to_markdown(report_record)
        media_type = "text/markdown; charset=utf-8"
        suffix = "md"
    else:
        body = _to_csv(report_record)
        media_type = "text/csv; charset=utf-8"
        suffix = "csv"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{suffix}"'},
    )


def _to_markdown(record: dict[str, Any]) -> str:
    summary = record["summary"]
    lines = [
        f"# Test generation report: {record['id']}",
        "",
        f"- Specification: `{record['specification_id']}`",
        f"- Name/version: {record['specification']['title']} / "
        f"{record['specification']['version']}",
        f"- Content SHA-256: `{record['specification']['content_hash']}`",
        f"- Policy: `{record['policy_version']}`",
        f"- Created: {record['created_at']}",
        f"- Operations: {summary['operation_count']}",
        f"- Candidates: {summary['candidate_count']}",
        f"- Endpoints with candidates: {summary['endpoints_with_candidates']}",
        "",
        "## Endpoint coverage",
    ]
    for endpoint in record["endpoints"]:
        operation = endpoint["operation"]
        lines.extend(
            [
                "",
                f"### {operation.get('method', '')} {operation.get('path', '')}",
                f"Candidates: {endpoint['candidate_count']}",
            ]
        )
        for candidate in endpoint["candidates"]:
            lines.extend(
                [
                    "",
                    f"- `{candidate['id']}` — {candidate['kind']}: {candidate['reason']}",
                    f"  - Status: {candidate['validation_status']}",
                    f"  - Mutation: `{json.dumps(candidate['mutation'], ensure_ascii=False)}`",
                ]
            )
    return "\n".join(lines) + "\n"


def _to_csv(record: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "report_id",
            "created_at",
            "policy_version",
            "method",
            "path",
            "candidate_id",
            "kind",
            "reason",
            "validation_status",
            "mutation",
        ]
    )
    for endpoint in record["endpoints"]:
        operation = endpoint["operation"]
        for candidate in endpoint["candidates"]:
            writer.writerow(
                [
                    record["id"],
                    record["created_at"],
                    record["policy_version"],
                    operation.get("method", ""),
                    operation.get("path", ""),
                    candidate["id"],
                    candidate["kind"],
                    candidate["reason"],
                    candidate["validation_status"],
                    json.dumps(candidate["mutation"], ensure_ascii=False),
                ]
            )
    return buffer.getvalue()
