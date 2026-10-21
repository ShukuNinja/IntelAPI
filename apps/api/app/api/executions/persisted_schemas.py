from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_id: UUID | None = None
    timeout_seconds: float = Field(default=10.0, gt=0, le=30)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    severity: str
    title: str
    message: str
    details: dict[str, object]
    created_at: datetime


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    saved_request_id: UUID | None
    environment_id: UUID | None
    status: str
    method: str
    url: str
    response_status_code: int | None
    response_headers: dict[str, str]
    response_body: str | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    evidence: list[EvidenceRead] = Field(default_factory=list)


class ExecutionListRead(BaseModel):
    items: list[ExecutionRead]
    total: int
    limit: int
    offset: int
