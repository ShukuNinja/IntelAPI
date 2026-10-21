"""Contracts for durable campaign operations."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.test_generation.models import CandidateCategory

CampaignState = Literal["queued", "running", "completed", "failed", "cancelled"]


class ORMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    saved_request_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=100)
    operation_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=20)
    categories: list[CandidateCategory] = Field(
        default_factory=lambda: [CandidateCategory.POSITIVE], max_length=5
    )
    environment_id: UUID | None = None
    max_executions: int = Field(default=100, ge=1, le=1000)
    max_iterations: int = Field(default=100, ge=1, le=1000)
    max_duration_seconds: int = Field(default=3600, ge=1, le=86400)

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()

    @model_validator(mode="after")
    def exactly_one_input_source(self) -> "CampaignCreate":
        if (self.saved_request_ids is None) == (self.operation_ids is None):
            raise ValueError("Provide saved_request_ids or operation_ids, not both.")
        if self.operation_ids is not None and self.environment_id is None:
            raise ValueError("An environment is required for OpenAPI operation campaigns.")
        if not self.categories:
            raise ValueError("At least one test category must be selected.")
        return self


class CampaignRead(ORMRead):
    id: UUID
    project_id: UUID
    name: str
    state: CampaignState
    configuration: dict[str, Any]
    budget_max_executions: int
    budget_max_iterations: int
    budget_max_duration_seconds: int
    started_at: datetime | None
    completed_at: datetime | None
    cancel_requested_at: datetime | None
    failure_code: str | None
    failure_summary: str | None
    created_at: datetime
    updated_at: datetime
    test_count: int = 0
    execution_count: int = 0


class CampaignListRead(BaseModel):
    items: list[CampaignRead]
    total: int
    limit: int
    offset: int


class TestCaseRead(ORMRead):
    id: UUID
    campaign_id: UUID
    candidate_key: str
    category: str
    title: str
    description: str | None
    request_override: dict[str, Any]
    expected_behavior: dict[str, Any] | None
    generation_provenance: str
    created_at: datetime


class CampaignEventRead(ORMRead):
    sequence_number: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class CampaignReportRead(BaseModel):
    campaign: CampaignRead
    tests: dict[str, int]
    executions: dict[str, int]
    findings: dict[str, int]
    events: list[CampaignEventRead]
