"""Persisted health checks and execution assertion results."""

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.health_checks.schemas import (
    AssertionResultRead,
    HealthCheckCreate,
    HealthCheckListRead,
    HealthCheckRead,
    HealthCheckRunRead,
    HealthCheckUpdate,
)
from app.db.session import get_db
from app.models.execution import Execution
from app.models.health_check import AssertionResult, HealthCheck
from app.models.project import Project
from app.models.saved_request import SavedRequest
from app.models.user import User
from app.modules.execution.service import execute_saved_request
from app.modules.findings.service import is_sensitive_target, record_assertion_findings

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Health check not found."}
    )


def _owned_check(db: Session, check_id: UUID, user_id: UUID) -> HealthCheck:
    row = db.scalar(
        select(HealthCheck)
        .join(Project)
        .where(
            HealthCheck.id == check_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if row is None:
        raise _not_found()
    return row


def _owned_request(db: Session, request_id: UUID, user_id: UUID) -> SavedRequest:
    row = db.scalar(
        select(SavedRequest)
        .join(Project)
        .where(
            SavedRequest.id == request_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "Saved request not found."},
        )
    return row


def _path_value(document: Any, path: str) -> Any:
    current = document
    for segment in path.removeprefix("$").lstrip(".").split("."):
        if not segment:
            continue
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return None
    return current


def _schema_violations(
    value: Any, schema: dict[str, Any], path: str = "$", depth: int = 0
) -> list[str]:
    if depth > 12:
        return [f"{path}: schema nesting exceeds the supported limit"]
    errors: list[str] = []
    expected_type = schema.get("type")
    type_matches = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if isinstance(expected_type, str) and expected_type in type_matches:
        if not type_matches[expected_type](value):
            return [f"{path}: expected {expected_type}"]
    elif isinstance(expected_type, list) and expected_type:
        if not any(kind in type_matches and type_matches[kind](value) for kind in expected_type):
            return [f"{path}: value does not match an allowed type"]

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: value is outside the declared enum")
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if not isinstance(branches, list):
            continue
        matches = sum(not _schema_violations(value, branch, path, depth + 1) for branch in branches)
        if keyword == "allOf" and matches != len(branches):
            errors.append(f"{path}: value does not match every allOf schema")
        elif keyword == "anyOf" and matches == 0:
            errors.append(f"{path}: value does not match any anyOf schema")
        elif keyword == "oneOf" and matches != 1:
            errors.append(f"{path}: value must match exactly one oneOf schema")
    negated = schema.get("not")
    if isinstance(negated, dict) and not _schema_violations(value, negated, path, depth + 1):
        errors.append(f"{path}: value matches a forbidden schema")
    if isinstance(value, dict):
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if isinstance(required, list):
            errors.extend(
                f"{path}.{name}: required property is missing"
                for name in required
                if name not in value
            )
        if isinstance(properties, dict):
            for name, child_schema in properties.items():
                if name in value and isinstance(child_schema, dict):
                    errors.extend(
                        _schema_violations(value[name], child_schema, f"{path}.{name}", depth + 1)
                    )
                    if len(errors) >= 20:
                        return errors[:20]
            extras = set(value) - set(properties)
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.extend(
                    f"{path}.{name}: additional property is not allowed" for name in sorted(extras)
                )
            elif isinstance(additional, dict):
                for name in sorted(extras):
                    errors.extend(
                        _schema_violations(value[name], additional, f"{path}.{name}", depth + 1)
                    )
                    if len(errors) >= 20:
                        return errors[:20]
        for keyword in ("minProperties", "maxProperties"):
            bound = schema.get(keyword)
            if isinstance(bound, int) and (
                len(value) < bound if keyword == "minProperties" else len(value) > bound
            ):
                errors.append(f"{path}: object violates {keyword}")
    if isinstance(value, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            if len(value) > 1000:
                return [f"{path}: array exceeds the response-schema validation item limit"]
            for index, item in enumerate(value[:1000]):
                errors.extend(_schema_violations(item, items_schema, f"{path}[{index}]", depth + 1))
                if len(errors) >= 20:
                    return errors[:20]
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            errors.append(f"{path}: string is shorter than minLength")
        if isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string is longer than maxLength")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), (int, float)) and value < schema["minimum"]:
            errors.append(f"{path}: number is below minimum")
        if isinstance(schema.get("maximum"), (int, float)) and value > schema["maximum"]:
            errors.append(f"{path}: number exceeds maximum")
        if (
            isinstance(schema.get("exclusiveMinimum"), (int, float))
            and value <= schema["exclusiveMinimum"]
        ):
            errors.append(f"{path}: number does not exceed exclusiveMinimum")
        if (
            isinstance(schema.get("exclusiveMaximum"), (int, float))
            and value >= schema["exclusiveMaximum"]
        ):
            errors.append(f"{path}: number is not below exclusiveMaximum")
        if isinstance(schema.get("multipleOf"), (int, float)) and value % schema["multipleOf"] != 0:
            errors.append(f"{path}: number is not a multipleOf value")
    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(f"{path}: array has fewer than minItems")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(f"{path}: array has more than maxItems")
        if schema.get("uniqueItems") is True:
            canonical = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(canonical) != len(set(canonical)):
                errors.append(f"{path}: array items are not unique")
    return errors[:20]


def _evaluate(definition: dict[str, Any], execution: Execution) -> list[AssertionResult]:
    try:
        response_json = json.loads(execution.response_body or "")
    except (json.JSONDecodeError, RecursionError):
        response_json = None
    results = []
    for assertion in definition["assertions"]:
        kind, expected, target = (
            assertion["type"],
            assertion.get("expected"),
            assertion.get("target"),
        )
        actual: Any = None
        if kind == "status_code":
            actual = execution.response_status_code
        elif kind == "json_path_equals" and target:
            actual = _path_value(response_json, target)
        elif kind == "header_equals" and target:
            actual = (execution.response_headers or {}).get(target.lower())
        elif kind in {"response_time_lte", "latency_threshold"}:
            actual = execution.duration_ms
        elif kind == "response_schema":
            violations = _schema_violations(response_json, expected)
            actual = {
                "valid": not violations,
                "violations": [
                    "[REDACTED]" if is_sensitive_target(item.split(":", 1)[0]) else item
                    for item in violations
                ],
            }
        passed = execution.status == "completed" and actual == expected
        if kind == "response_schema":
            passed = execution.status == "completed" and actual["valid"]
        if kind in {"response_time_lte", "latency_threshold"}:
            passed = (
                execution.status == "completed"
                and isinstance(actual, (int, float))
                and actual <= expected
            )
        safe_actual = "[REDACTED]" if is_sensitive_target(target) else actual
        results.append(
            AssertionResult(
                execution_id=execution.id,
                assertion_type=kind,
                passed=passed,
                expected=expected,
                actual=safe_actual,
                message=f"{kind} {'passed' if passed else 'failed'}"
                + (f" ({target})" if target else ""),
            )
        )
    return results


@router.get("/projects/{project_id}/health-checks", response_model=HealthCheckListRead)
def list_health_checks(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HealthCheckListRead:
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
    filters = HealthCheck.project_id == project_id
    total = db.scalar(select(func.count()).select_from(HealthCheck).where(filters)) or 0
    rows = db.scalars(
        select(HealthCheck)
        .where(filters)
        .order_by(HealthCheck.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return HealthCheckListRead(
        items=[HealthCheckRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/projects/{project_id}/health-checks",
    response_model=HealthCheckRead,
    status_code=status.HTTP_201_CREATED,
)
def create_health_check(
    project_id: UUID, payload: HealthCheckCreate, db: DbSession, current_user: CurrentUser
) -> HealthCheckRead:
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
    request = _owned_request(db, payload.saved_request_id, current_user.id)
    if request.project_id != project_id:
        raise HTTPException(
            status_code=422, detail="Saved request must belong to the selected project."
        )
    row = HealthCheck(
        project_id=project_id,
        saved_request_id=request.id,
        name=payload.name.strip(),
        enabled=payload.enabled,
        definition={"assertions": [item.model_dump() for item in payload.assertions]},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return HealthCheckRead.model_validate(row)


@router.get("/health-checks/{check_id}", response_model=HealthCheckRead)
def get_health_check(check_id: UUID, db: DbSession, current_user: CurrentUser) -> HealthCheckRead:
    return HealthCheckRead.model_validate(_owned_check(db, check_id, current_user.id))


@router.patch("/health-checks/{check_id}", response_model=HealthCheckRead)
def update_health_check(
    check_id: UUID, payload: HealthCheckUpdate, db: DbSession, current_user: CurrentUser
) -> HealthCheckRead:
    row = _owned_check(db, check_id, current_user.id)
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="At least one field must be supplied.")
    if "name" in payload.model_fields_set:
        if not payload.name:
            raise HTTPException(status_code=422, detail="Name cannot be null.")
        row.name = payload.name.strip()
    if "enabled" in payload.model_fields_set:
        if payload.enabled is None:
            raise HTTPException(status_code=422, detail="Enabled cannot be null.")
        row.enabled = payload.enabled
    if "assertions" in payload.model_fields_set:
        if payload.assertions is None:
            raise HTTPException(status_code=422, detail="Assertions cannot be null.")
        row.definition = {"assertions": [item.model_dump() for item in payload.assertions]}
    db.commit()
    db.refresh(row)
    return HealthCheckRead.model_validate(row)


@router.delete("/health-checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_health_check(check_id: UUID, db: DbSession, current_user: CurrentUser) -> None:
    db.delete(_owned_check(db, check_id, current_user.id))
    db.commit()


@router.post("/health-checks/{check_id}/run", response_model=HealthCheckRunRead)
def run_health_check(
    check_id: UUID, db: DbSession, current_user: CurrentUser
) -> HealthCheckRunRead:
    row = _owned_check(db, check_id, current_user.id)
    if not row.enabled:
        raise HTTPException(status_code=409, detail="Disabled health checks cannot be run.")
    if row.saved_request_id is None:
        raise HTTPException(status_code=409, detail="Health check has no saved request.")
    request = _owned_request(db, row.saved_request_id, current_user.id)
    execution = execute_saved_request(db, request, current_user.id, None, 10)
    results = _evaluate(row.definition, execution)
    for result in results:
        result.health_check_id = row.id
        db.add(result)
    db.flush()
    record_assertion_findings(db, row, execution, results)
    db.commit()
    status_value = (
        "unavailable"
        if execution.status != "completed"
        else "healthy"
        if all(item.passed for item in results)
        else "degraded"
    )
    return HealthCheckRunRead(
        health_check=HealthCheckRead.model_validate(row),
        execution_id=execution.id,
        status=status_value,
        assertions=[AssertionResultRead.model_validate(item) for item in results],
    )


@router.get("/health-checks/{check_id}/runs", response_model=list[AssertionResultRead])
@router.get("/health-checks/{check_id}/results", response_model=list[AssertionResultRead])
def list_health_check_results(
    check_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AssertionResultRead]:
    row = _owned_check(db, check_id, current_user.id)
    rows = db.execute(
        select(AssertionResult, Execution.status)
        .join(Execution, Execution.id == AssertionResult.execution_id)
        .where(AssertionResult.health_check_id == row.id)
        .order_by(AssertionResult.created_at.desc())
        .limit(limit)
    ).all()
    results = []
    for result, execution_status in rows:
        item = AssertionResultRead.model_validate(result)
        item.execution_status = execution_status
        results.append(item)
    return results
