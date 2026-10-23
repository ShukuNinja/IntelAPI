from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.modules.api_understanding.service import SpecificationError, generate_candidates, parse_specification

router = APIRouter(prefix="/specifications", tags=["specifications"])


class SpecificationInput(BaseModel):
    document: dict[str, Any]


class CandidatePreviewInput(BaseModel):
    operation: dict[str, Any]
    limit: int = Field(default=20, ge=1, le=100)


@router.post("/parse")
def parse_document(payload: SpecificationInput) -> dict[str, Any]:
    try:
        return parse_specification(payload.document)
    except SpecificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/candidates/preview")
def preview_candidates(payload: CandidatePreviewInput) -> dict[str, Any]:
    try:
        return {"candidates": generate_candidates(payload.operation, payload.limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
