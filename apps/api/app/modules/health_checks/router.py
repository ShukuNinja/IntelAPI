import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AssertionResultRecord, ExecutionRecord, HealthCheckRecord, SavedRequest
from app.modules.execution.service import ExecutionError, execute_request
from app.modules.test_generation.router import _project

router = APIRouter(prefix="/projects/{project_id}/health-checks", tags=["health-checks"])
JSON_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


class AssertionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["status_code", "latency_ms", "json_pointer", "header_equals", "response_schema"]
    status_code: int | None = Field(default=None, ge=100, le=599)
    max_ms: int | None = Field(default=None, ge=1, le=120_000)
    pointer: str | None = Field(default=None, max_length=512)
    operator: Literal["exists", "equals", "type"] | None = None
    expected: Any = None
    expected_type: str | None = None
    header: str | None = Field(default=None, max_length=64)
    response_schema: dict[str, Any] | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def validate_assertion(self) -> "AssertionInput":
        if self.type == "status_code" and self.status_code is None:
            raise ValueError("status_code assertions need status_code.")
        if self.type == "latency_ms" and self.max_ms is None:
            raise ValueError("latency_ms assertions need max_ms.")
        if self.type == "json_pointer":
            if not self.pointer or not self.pointer.startswith("/") or self.operator is None:
                raise ValueError("json_pointer assertions need a pointer and operator.")
            if re.search(r"~(?![01])", self.pointer):
                raise ValueError("JSON Pointer escapes must use ~0 or ~1.")
            if self.operator == "type" and self.expected_type not in JSON_TYPES:
                raise ValueError("JSON type assertions need a supported expected_type.")
            if self.operator == "equals" and len(json.dumps(self.expected)) > 4096:
                raise ValueError("JSON equality assertion values are limited to 4 KB.")
        if self.type == "header_equals":
            if not self.header or self.header.lower() not in {
                "content-type",
                "content-length",
                "date",
            }:
                raise ValueError("Only content-type, content-length, and date can be asserted.")
            if not isinstance(self.expected, str):
                raise ValueError("header_equals assertions need a string expected value.")
            if len(self.expected) > 4096:
                raise ValueError("Header assertion values are limited to 4 KB.")
        if self.type == "response_schema" and not self.response_schema:
            raise ValueError("response_schema assertions need a schema object.")
        if self.response_schema is not None and len(json.dumps(self.response_schema)) > 25_000:
            raise ValueError("Response schemas are limited to 25 KB.")
        return self


class HealthCheckInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    saved_request_id: UUID | None = None
    enabled: bool = True
    assertions: list[AssertionInput] = Field(min_length=1, max_length=20)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Health check name cannot be blank.")
        return value.strip()


def _check_response(check: HealthCheckRecord) -> dict[str, Any]:
    return {
        "id": str(check.id),
        "project_id": str(check.project_id),
        "name": check.name,
        "saved_request_id": str(check.saved_request_id) if check.saved_request_id else None,
        "enabled": check.enabled,
        "assertions": check.definition["assertions"],
        "created_at": check.created_at.isoformat() if check.created_at else None,
        "updated_at": check.updated_at.isoformat() if check.updated_at else None,
    }


def _validated_request(
    db: Session, project_id: UUID, saved_request_id: UUID | None
) -> SavedRequest:
    if saved_request_id is None:
        raise HTTPException(status_code=422, detail="Choose a saved request for this health check.")
    request = db.scalar(
        select(SavedRequest).where(
            SavedRequest.id == saved_request_id, SavedRequest.project_id == project_id
        )
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Saved request not found in this project.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        raise HTTPException(
            status_code=422,
            detail="Health checks are read-only and accept GET, HEAD, or OPTIONS requests.",
        )
    return request


@router.get("")
def list_health_checks(
    project_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    records = db.scalars(
        select(HealthCheckRecord)
        .where(HealthCheckRecord.project_id == project.id)
        .order_by(HealthCheckRecord.updated_at.desc())
    )
    return [_check_response(item) for item in records]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_health_check(
    project_id: UUID, payload: HealthCheckInput, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    project = _project(db, project_id)
    _validated_request(db, project.id, payload.saved_request_id)
    record = HealthCheckRecord(
        project_id=project.id,
        saved_request_id=payload.saved_request_id,
        name=payload.name,
        enabled=payload.enabled,
        definition={"assertions": [item.model_dump(by_alias=True) for item in payload.assertions]},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _check_response(record)


@router.patch("/{check_id}")
def update_health_check(
    project_id: UUID,
    check_id: UUID,
    payload: HealthCheckInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(HealthCheckRecord).where(
            HealthCheckRecord.id == check_id, HealthCheckRecord.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Health check not found.")
    _validated_request(db, project.id, payload.saved_request_id)
    record.name = payload.name
    record.saved_request_id = payload.saved_request_id
    record.enabled = payload.enabled
    record.definition = {
        "assertions": [item.model_dump(by_alias=True) for item in payload.assertions]
    }
    db.commit()
    db.refresh(record)
    return _check_response(record)


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_health_check(
    project_id: UUID, check_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> None:
    project = _project(db, project_id)
    record = db.scalar(
        select(HealthCheckRecord).where(
            HealthCheckRecord.id == check_id, HealthCheckRecord.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Health check not found.")
    db.delete(record)
    db.commit()


@router.post("/{check_id}/run")
async def run_health_check(
    project_id: UUID, check_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    project = _project(db, project_id)
    check = db.scalar(
        select(HealthCheckRecord).where(
            HealthCheckRecord.id == check_id, HealthCheckRecord.project_id == project.id
        )
    )
    if check is None:
        raise HTTPException(status_code=404, detail="Health check not found.")
    if not check.enabled:
        raise HTTPException(status_code=409, detail="This health check is disabled.")
    request = _validated_request(db, project.id, check.saved_request_id)
    started_at = datetime.now(UTC)
    safe_snapshot = {
        "method": request.method,
        "origin": "blocked",
        "health_check_id": str(check.id),
    }
    try:
        result = await execute_request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            body=request.body,
            confirm_unsafe=False,
        )
    except ExecutionError as exc:
        finished = datetime.now(UTC)
        record = ExecutionRecord(
            project_id=project.id,
            outcome=exc.outcome,
            request_snapshot=safe_snapshot,
            started_at=started_at,
            completed_at=finished,
            error_summary=str(exc)[:500],
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return {
            "execution_id": str(record.id),
            "outcome": exc.outcome,
            "status_code": None,
            "duration_ms": None,
            "passed": False,
            "assertions": [],
            "error": str(exc),
        }

    finished = datetime.now(UTC)
    safe_snapshot["origin"] = result["origin"]
    record = ExecutionRecord(
        project_id=project.id,
        outcome=result["outcome"],
        request_snapshot=safe_snapshot,
        status_code=result["status_code"],
        duration_ms=result["elapsed_ms"],
        response_headers=result["headers"],
        response_size_bytes=result["response_bytes"],
        started_at=started_at,
        completed_at=finished,
    )
    db.add(record)
    db.flush()
    evaluated = [
        _evaluate_assertion(assertion, result) for assertion in check.definition["assertions"]
    ]
    result_records = [
        AssertionResultRecord(
            execution_id=record.id,
            assertion_type=item["type"],
            passed=item["passed"],
            expected=item.get("expected"),
            actual=item.get("evidence"),
            message=item["message"],
        )
        for item in evaluated
    ]
    db.add_all(result_records)
    db.commit()
    return {
        "execution_id": str(record.id),
        "outcome": record.outcome,
        "status_code": record.status_code,
        "duration_ms": record.duration_ms,
        "passed": all(item["passed"] for item in evaluated),
        "assertions": evaluated,
    }


@router.get("/{check_id}/runs")
def list_health_check_runs(
    project_id: UUID,
    check_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    check = db.scalar(
        select(HealthCheckRecord).where(
            HealthCheckRecord.id == check_id, HealthCheckRecord.project_id == project.id
        )
    )
    if check is None:
        raise HTTPException(status_code=404, detail="Health check not found.")
    records = db.scalars(
        select(ExecutionRecord)
        .where(
            ExecutionRecord.project_id == project.id,
            ExecutionRecord.request_snapshot["health_check_id"].as_string() == str(check.id),
        )
        .order_by(ExecutionRecord.started_at.desc())
        .limit(limit)
    )
    output = []
    for record in records:
        assertions = db.scalars(
            select(AssertionResultRecord).where(AssertionResultRecord.execution_id == record.id)
        )
        result_items = [
            {
                "type": item.assertion_type,
                "passed": item.passed,
                "expected": item.expected,
                "evidence": item.actual,
                "message": item.message,
            }
            for item in assertions
        ]
        output.append(
            {
                "execution_id": str(record.id),
                "outcome": record.outcome,
                "status_code": record.status_code,
                "duration_ms": record.duration_ms,
                "passed": bool(result_items) and all(item["passed"] for item in result_items),
                "created_at": record.started_at.isoformat(),
                "assertions": result_items,
            }
        )
    return output


def _evaluate_assertion(assertion: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    kind = assertion["type"]
    expected: Any = None
    passed = False
    if kind == "status_code":
        expected = assertion["status_code"]
        passed = response["status_code"] == expected
    elif kind == "latency_ms":
        expected = assertion["max_ms"]
        passed = response["elapsed_ms"] <= expected
    elif kind == "header_equals":
        expected = assertion["expected"]
        actual = response["headers"].get(assertion["header"].lower())
        passed = actual == expected
        return {
            "type": kind,
            "expected": expected,
            "passed": passed,
            "message": (
                f"Response header {assertion['header']} "
                f"{'matched' if passed else 'did not match'} the configured value."
            ),
        }
    elif kind == "json_pointer":
        exists, value = _resolve_pointer(response["body"], assertion["pointer"])
        operator = assertion["operator"]
        expected = (
            assertion.get("expected_type") if operator == "type" else assertion.get("expected")
        )
        if operator == "exists":
            passed = exists
        elif operator == "equals":
            passed = exists and value == expected
        else:
            passed = exists and _value_type(value) == expected
        return {
            "type": kind,
            "expected": expected,
            "passed": passed,
            "message": (
                f"JSON pointer {assertion['pointer']} "
                f"{'matched' if passed else 'did not match'} its configured assertion."
            ),
        }
    elif kind == "response_schema":
        from app.modules.test_generation.router import _response_schema_mismatches

        mismatches, _ = _response_schema_mismatches(assertion["schema"], response["body"])
        passed = not mismatches
        return {
            "type": kind,
            "expected": "schema match",
            "passed": passed,
            "message": f"Response schema check found {len(mismatches)} mismatch(es).",
            "evidence": {"mismatches": mismatches},
            "mismatches": mismatches,
        }
    return {
        "type": kind,
        "expected": expected,
        "passed": passed,
        "message": f"Assertion {'passed' if passed else 'failed'}.",
    }


def _resolve_pointer(body: Any, pointer: str) -> tuple[bool, Any]:
    value = body
    for raw_token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw_token):
            return False, None
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and token.isdecimal() and int(token) < len(value):
            value = value[int(token)]
        else:
            return False, None
    return True, value


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"
