from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.modules.test_generation.models import CandidateCategory


class ORMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SpecificationImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=2_200_000)
    url: HttpUrl | None = None

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "SpecificationImport":
        if (self.content is None) == (self.url is None):
            raise ValueError("Provide exactly one of content or url.")
        return self


class SpecificationRead(ORMRead):
    id: UUID
    project_id: UUID
    created_by_user_id: UUID
    name: str
    source_kind: str
    source_url: str | None
    content_sha256: str
    spec_version: int
    openapi_version: str | None
    created_at: datetime
    operation_count: int


class SpecificationDetailRead(SpecificationRead):
    spec_document: dict[str, Any]


class SpecificationListRead(BaseModel):
    items: list[SpecificationRead]
    pagination: dict[str, int]


class OperationRead(ORMRead):
    id: UUID
    specification_id: UUID
    operation_key: str
    method: str
    path_template: str
    summary: str | None
    operation_document: dict[str, Any]
    created_at: datetime


class OperationListRead(BaseModel):
    items: list[OperationRead]
    pagination: dict[str, int]


class CandidatePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[CandidateCategory] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    llm: bool = False


class CandidateRead(BaseModel):
    candidate_id: str
    operation_key: str
    category: CandidateCategory
    title: str
    method: str
    path: str
    parameters: dict[str, Any]
    body: dict[str, Any] | None
    rationale: str


class CandidatePreviewRead(BaseModel):
    items: list[CandidateRead]
    persisted: Literal[False] = False
    llm_status: str
    llm_error: str | None = None


class KnowledgeFactRead(ORMRead):
    id: UUID
    fact_type: str
    subject: str
    fact_value: dict[str, Any]
    provenance: str
    confidence: float | None
    source_ref: dict[str, Any]
    created_at: datetime
