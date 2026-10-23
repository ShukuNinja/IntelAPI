from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.modules.api_understanding.service import (
    SpecificationError,
    generate_candidates,
    generate_generation_report,
    parse_specification,
    parse_specification_content,
)

router = APIRouter(prefix="/specifications", tags=["specifications"])


class SpecificationInput(BaseModel):
    document: dict[str, Any] | None = None
    content: str | None = Field(default=None, max_length=2_000_000)
    source_format: Literal["json", "yaml"] = "json"

    @model_validator(mode="after")
    def exactly_one_source(self) -> "SpecificationInput":
        if (self.document is None) == (self.content is None):
            raise ValueError("Provide exactly one of document or content.")
        return self


class CandidatePreviewInput(BaseModel):
    operation: dict[str, Any]
    limit: int = Field(default=20, ge=1, le=100)


class GenerationReportInput(BaseModel):
    operations: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    per_operation_limit: int = Field(default=20, ge=1, le=20)


@router.post("/parse")
def parse_document(payload: SpecificationInput) -> dict[str, Any]:
    try:
        if payload.document is not None:
            return parse_specification(payload.document)
        return parse_specification_content(payload.content or "", payload.source_format)
    except SpecificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/candidates/preview")
def preview_candidates(payload: CandidatePreviewInput) -> dict[str, Any]:
    try:
        return {"candidates": generate_candidates(payload.operation, payload.limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/candidates/report")
def generation_report(payload: GenerationReportInput) -> dict[str, Any]:
    try:
        return generate_generation_report(payload.operations, payload.per_operation_limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
