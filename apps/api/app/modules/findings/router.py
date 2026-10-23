from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExecutionReportRecord, FindingTriageRecord
from app.modules.test_generation.router import _project

router = APIRouter(prefix="/projects/{project_id}/findings", tags=["findings"])

Classification = Literal["confirmed", "false_positive", "accepted"]


class TriageInput(BaseModel):
    classification: Classification
    notes: str | None = Field(default=None, max_length=2000)


def _observations(report: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for index, finding in enumerate(report.get("contract_findings", [])):
        items.append(
            {
                "evidence_key": f"contract:{index}",
                "kind": finding.get("kind", "contract_observation"),
                "details": finding,
            }
        )
    for index, assertion in enumerate(report.get("assertions", [])):
        if assertion.get("passed") is False:
            items.append(
                {
                    "evidence_key": f"assertion:{index}",
                    "kind": assertion.get("kind", "failed_assertion"),
                    "details": assertion,
                }
            )
    return items


@router.get("")
def list_findings(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    records = db.scalars(
        select(ExecutionReportRecord)
        .where(ExecutionReportRecord.project_id == project.id)
        .order_by(ExecutionReportRecord.created_at.desc())
        .limit(200)
    )
    triage_records = db.scalars(
        select(FindingTriageRecord).where(FindingTriageRecord.project_id == project.id)
    )
    triage = {(item.execution_report_id, item.evidence_key): item for item in triage_records}
    result = []
    for record in records:
        report = record.report
        for observation in _observations(report):
            status_record = triage.get((record.id, observation["evidence_key"]))
            result.append(
                {
                    "id": f"{record.id}:{observation['evidence_key']}",
                    "execution_report_id": str(record.id),
                    "candidate_id": record.candidate_id,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "operation": report.get("operation", {}),
                    "execution": report.get("execution", {}),
                    "kind": observation["kind"],
                    "details": observation["details"],
                    "classification": status_record.classification
                    if status_record
                    else "untriaged",
                    "notes": status_record.notes if status_record else None,
                    "evidence_key": observation["evidence_key"],
                }
            )
    return result


@router.put("/{report_id}/{evidence_key}")
def update_finding_triage(
    project_id: UUID,
    report_id: UUID,
    evidence_key: str,
    payload: TriageInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    report = db.scalar(
        select(ExecutionReportRecord).where(
            ExecutionReportRecord.id == report_id,
            ExecutionReportRecord.project_id == project.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Execution report not found.")
    valid_keys = {item["evidence_key"] for item in _observations(report.report)}
    if evidence_key not in valid_keys:
        raise HTTPException(status_code=404, detail="Finding observation not found.")
    record = db.scalar(
        select(FindingTriageRecord).where(
            FindingTriageRecord.execution_report_id == report.id,
            FindingTriageRecord.evidence_key == evidence_key,
        )
    )
    if record is None:
        record = FindingTriageRecord(
            project_id=project.id,
            execution_report_id=report.id,
            evidence_key=evidence_key,
            classification=payload.classification,
            notes=payload.notes,
        )
        db.add(record)
    else:
        record.classification = payload.classification
        record.notes = payload.notes
    db.commit()
    return {
        "evidence_key": record.evidence_key,
        "classification": record.classification,
        "notes": record.notes,
    }
