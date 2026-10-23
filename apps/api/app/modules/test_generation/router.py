import copy
import csv
import io
import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AnyHttpUrl, BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ApiSpecification,
    ExecutionRecord,
    ExecutionReportRecord,
    GenerationReportRecord,
    Project,
    User,
)
from app.modules.adaptive.feedback import decide_follow_up
from app.modules.api_understanding.service import generate_candidates, generate_generation_report
from app.modules.execution.service import ExecutionError, execute_request
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}", tags=["test-generation"])


class GenerateReportInput(BaseModel):
    per_operation_limit: int = Field(default=20, ge=1, le=20)


class CandidateAssertionInput(BaseModel):
    kind: Literal["header_equals", "json_pointer_exists", "json_pointer_type"]
    name: str | None = Field(default=None, max_length=64)
    pointer: str | None = Field(default=None, max_length=512)
    expected: Any = None
    expected_type: (
        Literal["object", "array", "string", "number", "integer", "boolean", "null"] | None
    ) = None

    @model_validator(mode="after")
    def validate_assertion(self) -> "CandidateAssertionInput":
        if self.kind == "header_equals":
            if self.name is None or self.name.lower() not in {
                "content-type",
                "content-length",
                "date",
            }:
                raise ValueError(
                    "Header assertions support content-type, content-length, and date only."
                )
            if not isinstance(self.expected, str):
                raise ValueError("Header equality assertions require a string expected value.")
        else:
            if self.pointer is None or not self.pointer.startswith("/"):
                raise ValueError("JSON assertions require a JSON Pointer beginning with '/'.")
            if re.search(r"~(?![01])", self.pointer):
                raise ValueError("JSON Pointer escape sequences must use ~0 or ~1.")
            if self.kind == "json_pointer_type" and self.expected_type is None:
                raise ValueError("JSON type assertions require expected_type.")
        return self


class CandidateExecutionInput(BaseModel):
    base_url: AnyHttpUrl
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    path_parameters: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: dict[str, Any] | list[Any] | None = None
    confirm_unsafe: bool = False
    expected_status_code: int | None = Field(default=None, ge=100, le=599)
    follow_up_budget: int = Field(default=5, ge=0, le=20)
    assertions: list[CandidateAssertionInput] = Field(default_factory=list, max_length=20)


def _project(db: Session, project_id: UUID) -> Project:
    if get_settings().app_env.lower() == "production":
        raise HTTPException(
            status_code=503, detail="Local single-user reports are disabled in production."
        )
    user = db.scalar(select(User).where(User.google_sub == LOCAL_USER_SUB))
    project = (
        db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.owner_user_id == user.id,
                Project.deleted_at.is_(None),
            )
        )
        if user
        else None
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _report_response(record: GenerationReportRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "specification_id": str(record.specification_id),
        "created_at": record.created_at.isoformat(),
        **record.report,
    }


@router.post(
    "/specifications/{specification_id}/generation-reports",
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    project_id: UUID,
    specification_id: UUID,
    payload: GenerateReportInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id,
            ApiSpecification.project_id == project.id,
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    try:
        report = generate_generation_report(
            specification.normalized_operations,
            per_operation_limit=payload.per_operation_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["specification"] = {
        "id": str(specification.id),
        "title": specification.title,
        "version": specification.spec_version,
        "content_hash": specification.content_hash,
        "source_format": specification.source_format,
        "source_url": specification.source_url,
    }
    record = GenerationReportRecord(
        project_id=project.id,
        specification_id=specification.id,
        policy_version=report["policy_version"],
        report=report,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _report_response(record)


@router.post(
    "/specifications/{specification_id}/operations/{operation_id}/candidates/"
    "{candidate_id}/execute",
    status_code=status.HTTP_201_CREATED,
)
async def execute_candidate(
    project_id: UUID,
    specification_id: UUID,
    operation_id: str,
    candidate_id: str,
    payload: CandidateExecutionInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id,
            ApiSpecification.project_id == project.id,
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    operation = next(
        (item for item in specification.normalized_operations if item.get("id") == operation_id),
        None,
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found.")
    available_candidates = generate_candidates(operation, 100)
    candidate = next((item for item in available_candidates if item["id"] == candidate_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found for this operation.")
    candidate_ids = [item["id"] for item in available_candidates]
    previously_executed = set(
        db.scalars(
            select(ExecutionReportRecord.candidate_id)
            .where(
                ExecutionReportRecord.project_id == project.id,
                ExecutionReportRecord.candidate_id.in_(candidate_ids),
            )
            .distinct()
        )
    )
    follow_up_candidate_ids = [
        item_id for item_id in candidate_ids if item_id not in previously_executed
    ]

    base_url = str(payload.base_url).rstrip("/")
    parsed_base = urlsplit(base_url)
    if parsed_base.query or parsed_base.fragment:
        raise HTTPException(status_code=422, detail="Base URL cannot include a query or fragment.")
    path_parameters = dict(payload.path_parameters)
    query_parameters = dict(payload.query_parameters)
    headers = dict(payload.headers)
    body = copy.deepcopy(payload.body)
    mutation = candidate["mutation"]
    try:
        if "remove_parameter" in mutation:
            parameter = mutation["remove_parameter"]
            location, name = parameter["in"], parameter["name"]
            if location == "query":
                if name not in query_parameters:
                    raise ValueError(f"Provide a baseline query value for '{name}'.")
                query_parameters.pop(name)
            elif location == "path":
                raise ValueError("Path parameters cannot be omitted from a valid request URL.")
            elif location == "header":
                matching = next((key for key in headers if key.lower() == name.lower()), None)
                if matching is None:
                    raise ValueError(f"Provide a baseline header value for '{name}'.")
                headers.pop(matching)
            else:
                raise ValueError(
                    "Only query, path, and header parameter candidates are executable."
                )
        elif "set_parameter" in mutation:
            parameter = mutation["set_parameter"]
            location, name, value = parameter["in"], parameter["name"], parameter["value"]
            if location == "query":
                query_parameters[name] = value
            elif location == "path":
                path_parameters[name] = str(value)
            elif location == "header":
                headers[name] = str(value)
            else:
                raise ValueError(
                    "Only query, path, and header parameter candidates are executable."
                )
        elif "remove_property" in mutation:
            name = mutation["remove_property"]
            if not isinstance(body, dict) or name not in body:
                raise ValueError(f"Provide a baseline JSON body containing '{name}'.")
            body.pop(name)
        else:
            name, value = next(iter(mutation.items()))
            parameter = next(
                (item for item in operation.get("parameters", []) if item.get("name") == name),
                None,
            )
            if parameter is not None:
                location = parameter.get("in", "query")
                if location == "query":
                    query_parameters[name] = value
                elif location == "path":
                    path_parameters[name] = str(value)
                elif location == "header":
                    headers[name] = str(value)
                else:
                    raise ValueError("This parameter location cannot be executed.")
            elif isinstance(body, dict):
                body[name] = value
            else:
                raise ValueError("Provide a JSON object baseline body for this candidate.")

        path = operation["path"]
        for name in tuple(path_parameters):
            path = path.replace("{" + name + "}", quote(path_parameters.pop(name), safe=""))
        if "{" in path or "}" in path:
            raise ValueError("Provide values for all path parameters before execution.")
        url = base_url + "/" + path.lstrip("/")
        if query_parameters:
            url += "?" + urlencode(query_parameters, doseq=True)
        if len(url) > 4096:
            raise ValueError("The generated request URL exceeds the 4096 character limit.")
        body_text = json.dumps(body, separators=(",", ":")) if body is not None else None
        if body_text is not None and not any(key.lower() == "content-type" for key in headers):
            headers["Content-Type"] = "application/json"
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    started_at = datetime.now(UTC)
    safe_snapshot: dict[str, Any] = {
        "method": operation["method"],
        "origin": "blocked",
        "candidate_id": candidate_id,
    }
    try:
        result = await execute_request(
            method=operation["method"],
            url=url,
            headers=headers,
            body=body_text,
            confirm_unsafe=payload.confirm_unsafe,
        )
        safe_snapshot["origin"] = result["origin"]
    except ExecutionError as exc:
        completed_at = datetime.now(UTC)
        execution_record = ExecutionRecord(
            project_id=project.id,
            outcome=exc.outcome,
            request_snapshot=safe_snapshot,
            started_at=started_at,
            completed_at=completed_at,
            error_summary=str(exc)[:500],
        )
        db.add(execution_record)
        db.flush()
        run_report = _candidate_run_report(
            operation=operation,
            candidate=candidate,
            execution_id=str(execution_record.id),
            method=operation["method"],
            origin="blocked",
            status_code=None,
            elapsed_ms=None,
            response_bytes=None,
            response_headers={},
            response_body=None,
            expected_status_code=payload.expected_status_code,
            user_assertions=[item.model_dump() for item in payload.assertions],
            error=exc.outcome,
        )
        run_report["feedback"] = decide_follow_up(
            outcome=exc.outcome,
            assertions=run_report["assertions"],
            contract_findings=run_report["contract_findings"],
            candidate_ids=follow_up_candidate_ids,
            current_candidate_id=candidate_id,
            proposal_budget=payload.follow_up_budget,
        )
        db.add(
            ExecutionReportRecord(
                project_id=project.id,
                specification_id=specification.id,
                execution_id=execution_record.id,
                candidate_id=candidate_id,
                report=run_report,
            )
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    completed_at = datetime.now(UTC)
    record = ExecutionRecord(
        project_id=project.id,
        outcome=result["outcome"],
        request_snapshot=safe_snapshot,
        status_code=result["status_code"],
        duration_ms=result["elapsed_ms"],
        response_headers=result["headers"],
        response_size_bytes=result["response_bytes"],
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(record)
    db.flush()
    run_report = _candidate_run_report(
        operation=operation,
        candidate=candidate,
        execution_id=str(record.id),
        method=operation["method"],
        origin=result["origin"],
        status_code=result["status_code"],
        elapsed_ms=result["elapsed_ms"],
        response_bytes=result["response_bytes"],
        response_headers=result["headers"],
        response_body=result["body"],
        expected_status_code=payload.expected_status_code,
        user_assertions=[item.model_dump() for item in payload.assertions],
    )
    run_report["feedback"] = decide_follow_up(
        outcome=result["outcome"],
        assertions=run_report["assertions"],
        contract_findings=run_report["contract_findings"],
        candidate_ids=follow_up_candidate_ids,
        current_candidate_id=candidate_id,
        proposal_budget=payload.follow_up_budget,
    )
    report_record = ExecutionReportRecord(
        project_id=project.id,
        specification_id=specification.id,
        execution_id=record.id,
        candidate_id=candidate_id,
        report=run_report,
    )
    db.add(report_record)
    db.commit()
    db.refresh(record)
    db.refresh(report_record)
    return {
        **result,
        "id": str(record.id),
        "candidate_id": candidate_id,
        "run_report": _execution_report_response(report_record),
    }


def _candidate_run_report(
    *,
    operation: dict[str, Any],
    candidate: dict[str, Any],
    execution_id: str,
    method: str,
    origin: str,
    status_code: int | None,
    elapsed_ms: int | None,
    response_bytes: int | None,
    response_headers: dict[str, str],
    response_body: Any,
    expected_status_code: int | None,
    user_assertions: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    assertions = []
    if expected_status_code is not None:
        assertions.append(
            {
                "kind": "status_code",
                "expected": expected_status_code,
                "actual": status_code,
                "passed": status_code == expected_status_code,
            }
        )
    assertions.extend(
        _evaluate_candidate_assertion(
            assertion,
            status_code=status_code,
            response_headers=response_headers,
            response_body=response_body,
        )
        for assertion in user_assertions or []
    )
    declared_responses = operation.get("responses", {})
    status_text = str(status_code) if status_code is not None else ""
    status_family = f"{status_text[:1]}XX" if status_text else ""
    response_declared = (
        status_code is not None
        and isinstance(declared_responses, dict)
        and any(
            key in declared_responses
            for key in (status_text, "default", status_family, status_family.lower())
        )
    )
    contract_findings = []
    if status_code is not None and not response_declared:
        contract_findings.append(
            {
                "kind": "undocumented_status",
                "status_code": status_code,
                "classification": "contract_observation",
                "confirmed_defect": False,
            }
        )
    elif status_code is not None and isinstance(declared_responses, dict):
        response_key = next(
            (
                key
                for key in (status_text, status_family, status_family.lower(), "default")
                if key in declared_responses
            ),
            None,
        )
        response_definition = declared_responses.get(response_key, {}) if response_key else {}
        content = (
            response_definition.get("content", {}) if isinstance(response_definition, dict) else {}
        )
        declared_types = list(content) if isinstance(content, dict) else []
        actual_type = response_headers.get("content-type", "").split(";", 1)[0].strip().lower()
        compatible = any(
            expected == "*/*"
            or actual_type == expected.lower()
            or (expected.endswith("/*") and actual_type.startswith(expected[:-1].lower()))
            for expected in declared_types
        )
        if declared_types and actual_type and not compatible:
            contract_findings.append(
                {
                    "kind": "undocumented_content_type",
                    "expected_content_types": declared_types,
                    "actual_content_type": actual_type,
                    "classification": "contract_observation",
                    "confirmed_defect": False,
                }
            )
        schema = _response_schema(content, actual_type)
        if isinstance(schema, dict) and response_body is not None:
            mismatches, skipped = _response_schema_mismatches(schema, response_body)
            if mismatches:
                contract_findings.append(
                    {
                        "kind": "response_schema_mismatch",
                        "mismatches": mismatches,
                        "classification": "contract_observation",
                        "confirmed_defect": False,
                    }
                )
            if skipped:
                contract_findings.append(
                    {
                        "kind": "response_schema_check_partial",
                        "skipped_paths": skipped,
                        "classification": "analysis_limit",
                        "confirmed_defect": False,
                    }
                )
    report = {
        "report_type": "candidate_execution",
        "execution_id": execution_id,
        "candidate": {
            "id": candidate["id"],
            "kind": candidate["kind"],
            "reason": candidate["reason"],
            "mutation": candidate["mutation"],
        },
        "operation": {
            "id": operation["id"],
            "method": method,
            "path": operation["path"],
            "summary": operation.get("summary", ""),
        },
        "execution": {
            "origin": origin,
            "outcome": error or "http_response",
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "response_bytes": response_bytes,
            "response_headers": response_headers,
            "response_body_persisted": False,
        },
        "assertions": assertions,
        "contract_findings": contract_findings,
        "next_action": (
            "Review the target response against the declared contract; this observation alone "
            "does not confirm a defect."
            if contract_findings
            else "Review the response and add an explicit assertion if a contract check is needed."
        ),
    }
    return report


def _evaluate_candidate_assertion(
    assertion: dict[str, Any],
    *,
    status_code: int | None,
    response_headers: dict[str, str],
    response_body: Any,
) -> dict[str, Any]:
    kind = assertion["kind"]
    if status_code is None:
        return {"kind": kind, "passed": None, "evaluated": False}
    if kind == "header_equals":
        name = assertion["name"].lower()
        actual = response_headers.get(name)
        return {
            "kind": kind,
            "name": name,
            "expected": assertion["expected"],
            "actual": actual,
            "passed": actual == assertion["expected"],
        }

    pointer = assertion["pointer"]
    value: Any = response_body
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and token.isdecimal() and int(token) < len(value):
            value = value[int(token)]
        else:
            value = _MISSING_ASSERTION_VALUE
            break
    exists = value is not _MISSING_ASSERTION_VALUE
    result = {"kind": kind, "pointer": pointer, "actual_present": exists}
    if kind == "json_pointer_exists":
        result["passed"] = exists
        return result
    expected_type = assertion["expected_type"]
    actual_type = _json_value_type(value) if exists else None
    if expected_type == "integer":
        passed = isinstance(value, int) and not isinstance(value, bool)
    elif expected_type == "number":
        passed = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        passed = actual_type == expected_type
    result.update(
        {
            "expected_type": expected_type,
            "actual_type": actual_type,
            "passed": passed if exists else False,
        }
    )
    return result


def _json_value_type(value: Any) -> str:
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


_MISSING_ASSERTION_VALUE = object()


def _response_schema(content: Any, actual_type: str) -> dict[str, Any] | None:
    if not isinstance(content, dict):
        return None
    exact = next(
        (
            value
            for content_type, value in content.items()
            if str(content_type).lower() == actual_type
        ),
        {},
    )
    if not exact:
        exact = next(
            (
                value
                for content_type, value in content.items()
                if isinstance(content_type, str)
                and content_type.endswith("/*")
                and actual_type.startswith(content_type[:-1].lower())
            ),
            {},
        )
    schema = exact.get("schema") if isinstance(exact, dict) else None
    return schema if isinstance(schema, dict) else None


def _response_schema_mismatches(
    schema: dict[str, Any], value: Any
) -> tuple[list[dict[str, str]], list[str]]:
    mismatches: list[dict[str, str]] = []
    skipped: list[str] = []
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
        "null": type(None),
    }

    def visit(current_schema: Any, current: Any, path: str, depth: int) -> None:
        if len(mismatches) >= 20:
            return
        if depth > 12:
            skipped.append(path)
            return
        if not isinstance(current_schema, dict):
            skipped.append(path)
            return
        if "$ref" in current_schema or any(
            keyword in current_schema for keyword in ("allOf", "oneOf", "anyOf", "not")
        ):
            skipped.append(path)
            return
        if current_schema.get("nullable") is True and current is None:
            return
        expected_type = current_schema.get("type")
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        expected_types = [item for item in expected_types if isinstance(item, str)]
        if expected_types:
            matches = False
            for item in expected_types:
                if item == "integer" and isinstance(current, int) and not isinstance(current, bool):
                    matches = True
                elif (
                    item == "number"
                    and isinstance(current, (int, float))
                    and not isinstance(current, bool)
                ):
                    matches = True
                elif item in type_map and isinstance(current, type_map[item]):
                    matches = True
            if not matches:
                mismatches.append(
                    {"path": path, "rule": "type", "expected": "|".join(expected_types)}
                )
                return
        enum = current_schema.get("enum")
        if isinstance(enum, list) and current not in enum:
            mismatches.append({"path": path, "rule": "enum", "expected": "declared enum value"})
        if isinstance(current, dict):
            required = current_schema.get("required", [])
            if isinstance(required, list):
                for name in required:
                    if isinstance(name, str) and name not in current:
                        mismatches.append(
                            {"path": f"{path}/{name}", "rule": "required", "expected": "present"}
                        )
            properties = current_schema.get("properties", {})
            if isinstance(properties, dict):
                for name, child in properties.items():
                    if name in current:
                        visit(child, current[name], f"{path}/{name}", depth + 1)
            if current_schema.get("additionalProperties") is False and isinstance(properties, dict):
                for name in current.keys() - properties.keys():
                    mismatches.append(
                        {
                            "path": f"{path}/{name}",
                            "rule": "additionalProperties",
                            "expected": "not present",
                        }
                    )
        elif isinstance(current, list):
            item_schema = current_schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(current):
                    visit(item_schema, item, f"{path}/{index}", depth + 1)
                    if len(mismatches) >= 20:
                        break
        if isinstance(current, str):
            for keyword, compare in (
                ("minLength", lambda n: len(current) < n),
                ("maxLength", lambda n: len(current) > n),
            ):
                bound = current_schema.get(keyword)
                if isinstance(bound, int) and compare(bound):
                    mismatches.append({"path": path, "rule": keyword, "expected": str(bound)})
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            for keyword, compare in (
                ("minimum", lambda n: current < n),
                ("maximum", lambda n: current > n),
            ):
                bound = current_schema.get(keyword)
                if isinstance(bound, (int, float)) and compare(bound):
                    mismatches.append({"path": path, "rule": keyword, "expected": str(bound)})

    visit(schema, value, "$", 0)
    return mismatches[:20], sorted(set(skipped))[:20]


def _execution_report_response(record: ExecutionReportRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "specification_id": str(record.specification_id),
        "candidate_id": record.candidate_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        **record.report,
    }


@router.get("/execution-reports")
def list_execution_reports(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    return [
        {
            "id": str(record.id),
            "project_id": str(record.project_id),
            "specification_id": str(record.specification_id),
            "candidate_id": record.candidate_id,
            "created_at": record.created_at.isoformat(),
            "status_code": record.report["execution"]["status_code"],
        }
        for record in db.scalars(
            select(ExecutionReportRecord)
            .where(ExecutionReportRecord.project_id == project.id)
            .order_by(ExecutionReportRecord.created_at.desc())
            .limit(limit)
        )
    ]


@router.get("/execution-reports/{report_id}")
def get_execution_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(ExecutionReportRecord).where(
            ExecutionReportRecord.id == report_id,
            ExecutionReportRecord.project_id == project.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Execution report not found.")
    return _execution_report_response(record)


@router.get("/execution-reports/{report_id}/export")
def export_execution_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown", "csv"] = Query(),
) -> Response:
    report = get_execution_report(project_id, report_id, db)
    if format == "json":
        body = json.dumps(report, ensure_ascii=False, indent=2)
        media_type, suffix = "application/json", "json"
    elif format == "markdown":
        body = _execution_report_markdown(report)
        media_type, suffix = "text/markdown; charset=utf-8", "md"
    else:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "report_id",
                "execution_id",
                "candidate_id",
                "status_code",
                "elapsed_ms",
                "assertion",
                "passed",
                "contract_finding",
                "evidence_path",
                "rule",
                "expected",
                "feedback_action",
                "feedback_proposals",
            ]
        )
        assertions = report["assertions"] or [None]
        findings = report["contract_findings"] or [None]
        for assertion in assertions:
            for finding in findings:
                mismatches = (finding or {}).get("mismatches") or [None]
                for mismatch in mismatches:
                    writer.writerow(
                        [
                            report["id"],
                            report["execution_id"],
                            report["candidate_id"],
                            report["execution"]["status_code"],
                            report["execution"]["elapsed_ms"],
                            assertion["kind"] if assertion else "",
                            assertion["passed"] if assertion else "",
                            finding["kind"] if finding else "",
                            mismatch["path"] if mismatch else "",
                            mismatch["rule"] if mismatch else "",
                            mismatch["expected"] if mismatch else "",
                            report.get("feedback", {}).get("action", ""),
                            ";".join(report.get("feedback", {}).get("proposed_candidate_ids", [])),
                        ]
                    )
        body = buffer.getvalue()
        media_type, suffix = "text/csv; charset=utf-8", "csv"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="execution-report-{report_id}.{suffix}"'
        },
    )


def _execution_report_markdown(report: dict[str, Any]) -> str:
    execution = report["execution"]
    lines = [
        f"# Candidate execution report {report['id']}",
        "",
        f"- Execution: `{report['execution_id']}`",
        f"- Candidate: `{report['candidate_id']}` ({report['candidate']['kind']})",
        f"- Operation: `{report['operation']['method']} {report['operation']['path']}`",
        f"- Outcome: `{execution['outcome']}`",
        f"- Status: `{execution['status_code']}`",
        f"- Duration: `{execution['elapsed_ms']} ms`",
        "- Response body persisted: no",
        "",
        "## Assertions",
    ]
    lines.extend(_assertion_markdown(assertion) for assertion in report["assertions"])
    lines.append("\n## Contract observations")
    lines.extend(
        f"- {finding['kind']} at status `{finding.get('status_code', execution['status_code'])}`; "
        f"classification `{finding['classification']}`, confirmed defect: no"
        for finding in report["contract_findings"]
    )
    for finding in report["contract_findings"]:
        lines.extend(
            f"  - `{item['path']}`: `{item['rule']}` expected `{item['expected']}`"
            for item in finding.get("mismatches", [])
        )
        lines.extend(
            f"  - Schema check skipped at `{path}`." for path in finding.get("skipped_paths", [])
        )
    feedback = report.get("feedback")
    if feedback:
        lines.extend(
            [
                "",
                "## Feedback decision",
                f"- Action: `{feedback['action']}`",
                f"- Reason: {feedback['reason']}",
                f"- Proposal budget: {feedback['proposal_budget']}",
                f"- Proposed candidate IDs: "
                f"`{', '.join(feedback['proposed_candidate_ids']) or 'none'}`",
                "- Automatic execution: no",
            ]
        )
    lines.extend(["", f"Next action: {report['next_action']}"])
    return "\n".join(lines) + "\n"


@router.get("/generation-reports")
def list_reports(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    return [
        {
            "id": str(record.id),
            "specification_id": str(record.specification_id),
            "policy_version": record.policy_version,
            "candidate_count": record.report["summary"]["candidate_count"],
            "operation_count": record.report["summary"]["operation_count"],
            "created_at": record.created_at.isoformat(),
        }
        for record in db.scalars(
            select(GenerationReportRecord)
            .where(GenerationReportRecord.project_id == project.id)
            .order_by(GenerationReportRecord.created_at.desc())
            .limit(limit)
        )
    ]


@router.get("/generation-reports/{report_id}")
def get_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    record = db.scalar(
        select(GenerationReportRecord).where(
            GenerationReportRecord.id == report_id,
            GenerationReportRecord.project_id == project.id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Generation report not found.")
    return _report_response(record)


@router.get("/generation-reports/{report_id}/export")
def export_report(
    project_id: UUID,
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown", "csv"] = Query(),
) -> Response:
    report_record = get_report(project_id, report_id, db)
    filename = f"generation-report-{report_id}"
    if format == "json":
        body = json.dumps(report_record, ensure_ascii=False, indent=2)
        media_type = "application/json"
        suffix = "json"
    elif format == "markdown":
        body = _to_markdown(report_record)
        media_type = "text/markdown; charset=utf-8"
        suffix = "md"
    else:
        body = _to_csv(report_record)
        media_type = "text/csv; charset=utf-8"
        suffix = "csv"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{suffix}"'},
    )


def _to_markdown(record: dict[str, Any]) -> str:
    summary = record["summary"]
    lines = [
        f"# Test generation report: {record['id']}",
        "",
        f"- Specification: `{record['specification_id']}`",
        f"- Name/version: {record['specification']['title']} / "
        f"{record['specification']['version']}",
        f"- Content SHA-256: `{record['specification']['content_hash']}`",
        f"- Policy: `{record['policy_version']}`",
        f"- Created: {record['created_at']}",
        f"- Operations: {summary['operation_count']}",
        f"- Candidates: {summary['candidate_count']}",
        f"- Endpoints with candidates: {summary['endpoints_with_candidates']}",
        "",
        "## Endpoint coverage",
    ]
    for endpoint in record["endpoints"]:
        operation = endpoint["operation"]
        lines.extend(
            [
                "",
                f"### {operation.get('method', '')} {operation.get('path', '')}",
                f"Candidates: {endpoint['candidate_count']}",
            ]
        )
        for candidate in endpoint["candidates"]:
            lines.extend(
                [
                    "",
                    f"- `{candidate['id']}` — {candidate['kind']}: {candidate['reason']}",
                    f"  - Status: {candidate['validation_status']}",
                    f"  - Mutation: `{json.dumps(candidate['mutation'], ensure_ascii=False)}`",
                ]
            )
    return "\n".join(lines) + "\n"


def _assertion_markdown(assertion: dict[str, Any]) -> str:
    if assertion["kind"] == "status_code":
        detail = f"expected `{assertion['expected']}`, observed `{assertion['actual']}`"
    elif assertion["kind"] == "header_equals":
        detail = (
            f"header `{assertion['name']}` expected `{assertion['expected']}`, "
            f"observed `{assertion['actual']}`"
        )
    else:
        detail = f"pointer `{assertion['pointer']}`"
        if "expected_type" in assertion:
            detail += (
                f" expected type `{assertion['expected_type']}`, "
                f"observed `{assertion['actual_type']}`"
            )
        else:
            detail += f" present `{assertion['actual_present']}`"
    return f"- {assertion['kind']}: {detail}, passed `{assertion['passed']}`"


def _to_csv(record: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "report_id",
            "created_at",
            "policy_version",
            "method",
            "path",
            "candidate_id",
            "kind",
            "reason",
            "validation_status",
            "mutation",
        ]
    )
    for endpoint in record["endpoints"]:
        operation = endpoint["operation"]
        for candidate in endpoint["candidates"]:
            writer.writerow(
                [
                    record["id"],
                    record["created_at"],
                    record["policy_version"],
                    operation.get("method", ""),
                    operation.get("path", ""),
                    candidate["id"],
                    candidate["kind"],
                    candidate["reason"],
                    candidate["validation_status"],
                    json.dumps(candidate["mutation"], ensure_ascii=False),
                ]
            )
    return buffer.getvalue()
