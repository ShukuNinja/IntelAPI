"""Wire contracts for experiment setup and comparison results."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.test_generation import CandidateCategory, GenerationApproach


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    operation_ids: list[UUID] = Field(min_length=1, max_length=20)
    environment_id: UUID
    approaches: list[GenerationApproach] = Field(min_length=1, max_length=4)
    categories: list[CandidateCategory] = Field(
        default_factory=lambda: [
            CandidateCategory.POSITIVE,
            CandidateCategory.NEGATIVE,
            CandidateCategory.BOUNDARY,
            CandidateCategory.SCHEMA,
        ],
        min_length=1,
        max_length=5,
    )
    use_llm: bool = False
    llm_provider: Literal["nvidia", "groq"] | None = None
    llm_model: str | None = Field(default=None, min_length=1, max_length=160)
    max_executions: int = Field(default=100, ge=1, le=1000)
    max_iterations: int = Field(default=100, ge=1, le=1000)
    max_duration_seconds: int = Field(default=1800, ge=1, le=86400)

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()

    @field_validator("llm_model")
    @classmethod
    def non_blank_model(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Model cannot be blank.")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_unique_selections(self) -> "ExperimentCreate":
        for field_name in ("operation_ids", "approaches", "categories"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must be unique.")
        return self


class ExperimentRunRead(BaseModel):
    id: UUID
    campaign_id: UUID
    approach: GenerationApproach
    state: str
    configuration: dict[str, Any]
    generation_metadata: dict[str, Any]
    candidate_count: int
    execution_count: int


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    specification_id: UUID
    name: str
    configuration: dict[str, Any]
    state: str
    created_at: datetime
    updated_at: datetime
    runs: list[ExperimentRunRead] = Field(default_factory=list)


class ExperimentListRead(BaseModel):
    items: list[ExperimentRead]
    total: int
    limit: int
    offset: int


class ExperimentComparisonRead(BaseModel):
    experiment: ExperimentRead
    metrics_by_approach: dict[str, dict[str, Any]]
