import copy
import csv
import io
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import ApiSpecification, ExecutionRecord, GenerationReportRecord, Project, User
from app.modules.api_understanding.service import generate_candidates, generate_generation_report
from app.modules.execution.service import ExecutionError, execute_request
from app.modules.projects.router import LOCAL_USER_SUB

router = APIRouter(prefix="/projects/{project_id}", tags=["test-generation"])


class GenerateReportInput(BaseModel):
    per_operation_limit: int = Field(default=20, ge=1, le=20)


class CandidateExecutionInput(BaseModel):
    base_url: AnyHttpUrl
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    path_parameters: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: dict[str, Any] | list[Any] | None = None
    confirm_unsafe: bool = False


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
    candidate = next(
        (item for item in generate_candidates(operation, 100) if item["id"] == candidate_id),
        None,
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found for this operation.")

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
        db.add(
            ExecutionRecord(
                project_id=project.id,
                outcome=exc.outcome,
                request_snapshot=safe_snapshot,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error_summary=str(exc)[:500],
            )
        )
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = ExecutionRecord(
        project_id=project.id,
        outcome=result["outcome"],
        request_snapshot=safe_snapshot,
        status_code=result["status_code"],
        duration_ms=result["elapsed_ms"],
        response_headers=result["headers"],
        response_size_bytes=result["response_bytes"],
        started_at=started_at,
        completed_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {**result, "id": str(record.id), "candidate_id": candidate_id}


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
