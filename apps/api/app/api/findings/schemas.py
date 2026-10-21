"""Finding triage and evidence response contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FindingStatus = Literal["open", "confirmed", "accepted", "resolved", "false_positive"]
Severity = Literal["low", "medium", "high", "critical"]


class ORMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FindingRead(ORMRead):
    id: UUID
    project_id: UUID
    campaign_id: UUID | None
    test_case_id: UUID | None
    execution_id: UUID | None
    finding_key: str
    title: str
    summary: str
    classification: str
    machine_severity: str
    confidence: float | None
    user_status: FindingStatus
    user_severity: Severity | None
    triage_note: str | None
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0


class FindingListRead(BaseModel):
    items: list[FindingRead]
    total: int
    limit: int
    offset: int


class FindingTriageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_status: FindingStatus | None = None
    user_severity: Severity | None = None
    triage_note: str | None = Field(default=None, max_length=5000)


class EvidenceReferenceRead(ORMRead):
    id: UUID
    project_id: UUID
    finding_id: UUID | None
    execution_id: UUID | None
    assertion_result_id: UUID | None
    specification_id: UUID | None
    operation_id: UUID | None
    knowledge_fact_id: UUID | None
    provenance: str
    evidence_type: str
    excerpt: str | None
    evidence_metadata: dict[str, Any]
    created_at: datetime
