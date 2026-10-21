"""Evidence-backed findings with user-owned triage fields."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.findings.schemas import (
    EvidenceReferenceRead,
    FindingListRead,
    FindingRead,
    FindingTriageUpdate,
)
from app.db.session import get_db
from app.models.finding import EvidenceReference, Finding
from app.models.project import Project
from app.models.user import User

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Finding not found."}
    )


def _owned_finding(db: Session, finding_id: UUID, user_id: UUID) -> Finding:
    row = db.scalar(
        select(Finding)
        .join(Project)
        .where(
            Finding.id == finding_id, Project.owner_user_id == user_id, Project.deleted_at.is_(None)
        )
    )
    if row is None:
        raise _not_found()
    return row


def _read(db: Session, row: Finding) -> FindingRead:
    count = (
        db.scalar(
            select(func.count())
            .select_from(EvidenceReference)
            .where(EvidenceReference.finding_id == row.id)
        )
        or 0
    )
    return FindingRead(
        id=row.id,
        project_id=row.project_id,
        campaign_id=row.campaign_id,
        test_case_id=row.test_case_id,
        execution_id=row.execution_id,
        finding_key=row.finding_key,
        title=row.title,
        summary=row.summary,
        classification=row.classification,
        machine_severity=row.machine_severity,
        confidence=float(row.confidence) if row.confidence is not None else None,
        user_status=row.user_status,
        user_severity=row.user_severity,
        triage_note=row.triage_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
        evidence_count=count,
    )


@router.get("/projects/{project_id}/findings", response_model=FindingListRead)
def list_findings(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_status: str | None = None,
    severity: str | None = None,
) -> FindingListRead:
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
    filters = [Finding.project_id == project_id]
    if user_status:
        filters.append(Finding.user_status == user_status)
    if severity:
        filters.append(
            func.coalesce(Finding.user_severity, Finding.machine_severity) == severity.lower()
        )
    total = db.scalar(select(func.count()).select_from(Finding).where(*filters)) or 0
    rows = db.scalars(
        select(Finding)
        .where(*filters)
        .order_by(Finding.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return FindingListRead(
        items=[_read(db, row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/findings/{finding_id}", response_model=FindingRead)
def get_finding(finding_id: UUID, db: DbSession, current_user: CurrentUser) -> FindingRead:
    return _read(db, _owned_finding(db, finding_id, current_user.id))


@router.patch("/findings/{finding_id}", response_model=FindingRead)
def update_finding(
    finding_id: UUID, payload: FindingTriageUpdate, db: DbSession, current_user: CurrentUser
) -> FindingRead:
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="At least one triage field must be supplied.")
    row = _owned_finding(db, finding_id, current_user.id)
    if "user_status" in payload.model_fields_set:
        if payload.user_status is None:
            raise HTTPException(status_code=422, detail="user_status cannot be null.")
        row.user_status = payload.user_status
    if "user_severity" in payload.model_fields_set:
        row.user_severity = payload.user_severity
    if "triage_note" in payload.model_fields_set:
        row.triage_note = payload.triage_note
    db.commit()
    db.refresh(row)
    return _read(db, row)


@router.get("/findings/{finding_id}/evidence", response_model=list[EvidenceReferenceRead])
def list_finding_evidence(
    finding_id: UUID, db: DbSession, current_user: CurrentUser
) -> list[EvidenceReferenceRead]:
    _owned_finding(db, finding_id, current_user.id)
    rows = db.scalars(
        select(EvidenceReference)
        .where(EvidenceReference.finding_id == finding_id)
        .order_by(EvidenceReference.created_at, EvidenceReference.id)
    ).all()
    return [EvidenceReferenceRead.model_validate(row) for row in rows]


@router.get("/evidence/{evidence_id}", response_model=EvidenceReferenceRead)
def get_evidence(
    evidence_id: UUID, db: DbSession, current_user: CurrentUser
) -> EvidenceReferenceRead:
    row = db.scalar(
        select(EvidenceReference)
        .join(Project)
        .where(
            EvidenceReference.id == evidence_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Evidence not found."}
        )
    return EvidenceReferenceRead.model_validate(row)
