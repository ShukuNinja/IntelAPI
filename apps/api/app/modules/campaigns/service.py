"""Durable, bounded campaign processing shared by the worker and tests."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.secret_storage import (
    SecretStorageError,
    decrypt_environment_values,
    encrypt_environment_values,
)
from app.models import (
    CampaignEventRecord,
    CampaignJobRecord,
    CampaignRecord,
    Environment,
    ExecutionRecord,
    TestCaseRecord,
)
from app.modules.execution.service import ExecutionError, execute_request

LEASE_SECONDS = 120
TERMINAL_STATES = {"completed", "failed", "cancelled"}
_TEMPLATE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def append_event(db: Session, campaign_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
    db.scalar(select(CampaignRecord).where(CampaignRecord.id == campaign_id).with_for_update())
    sequence = (
        db.scalar(
            select(func.max(CampaignEventRecord.sequence_number)).where(
                CampaignEventRecord.campaign_id == campaign_id
            )
        )
        or 0
    )
    db.add(
        CampaignEventRecord(
            campaign_id=campaign_id,
            sequence_number=sequence + 1,
            event_type=event_type,
            payload=payload,
        )
    )


def campaign_report(db: Session, campaign: CampaignRecord) -> dict[str, Any]:
    cases = list(
        db.scalars(
            select(TestCaseRecord)
            .where(TestCaseRecord.campaign_id == campaign.id)
            .order_by(TestCaseRecord.created_at, TestCaseRecord.id)
        )
    )
    outcomes: dict[str, int] = {}
    for case in cases:
        outcome = (case.result or {}).get("outcome", case.state)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return {
        "campaign": _campaign_read(campaign),
        "summary": {
            "test_count": len(cases),
            "completed_count": sum(
                case.state in {"completed", "skipped", "inconclusive"} for case in cases
            ),
            "execution_count": sum(case.execution_id is not None for case in cases),
            "outcomes": outcomes,
            "termination_reason": campaign.failure_code
            or ("cancelled" if campaign.state == "cancelled" else None),
        },
        "tests": [_test_case_read(case) for case in cases],
    }


def _campaign_read(campaign: CampaignRecord) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "project_id": str(campaign.project_id),
        "name": campaign.name,
        "state": campaign.state,
        "created_at": campaign.created_at.isoformat(),
        "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
        "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
        "cancel_requested_at": (
            campaign.cancel_requested_at.isoformat() if campaign.cancel_requested_at else None
        ),
        "budget": {
            "max_executions": campaign.budget_max_executions,
            "max_iterations": campaign.budget_max_iterations,
            "max_duration_seconds": campaign.budget_max_duration_seconds,
        },
    }


def _test_case_read(case: TestCaseRecord) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "candidate_key": case.candidate_key,
        "operation_id": case.operation_id,
        "category": case.category,
        "title": case.title,
        "state": case.state,
        "execution_id": str(case.execution_id) if case.execution_id else None,
        "result": case.result,
    }


def _request_for_case(case: TestCaseRecord, config: dict[str, Any]) -> dict[str, Any]:
    override = case.request_override
    operation = override["operation"]
    candidate = override["candidate"]
    baseline = config.get("baseline_by_operation", {}).get(case.operation_id, {})
    if not isinstance(baseline, dict):
        raise ValueError("Baseline values must be an object.")
    query_values = baseline.get("query_parameters", {})
    path_values = baseline.get("path_parameters", {})
    header_values = baseline.get("headers", {})
    if not all(isinstance(item, dict) for item in (query_values, path_values, header_values)):
        raise ValueError("Baseline query, path, and header values must be objects.")
    query = dict(query_values)
    path_parameters = {key: str(value) for key, value in path_values.items()}
    headers = dict(header_values)
    if len(headers) > 100 or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or not key.strip()
        or "\r" in key
        or "\n" in key
        or "\r" in value
        or "\n" in value
        for key, value in headers.items()
    ):
        raise ValueError("Baseline headers are invalid or exceed the 100 header limit.")
    body = baseline.get("body")
    if isinstance(body, (dict, list)):
        body = json.loads(json.dumps(body))
    elif body is not None:
        raise ValueError("Baseline body must be a JSON object or array.")
    mutation = candidate.get("mutation", {})
    if "remove_parameter" in mutation:
        item = mutation["remove_parameter"]
        {"query": query, "path": path_parameters, "header": headers}.get(item.get("in"), {}).pop(
            item.get("name"), None
        )
    elif "set_parameter" in mutation:
        item = mutation["set_parameter"]
        location, name, value = item.get("in"), item.get("name"), item.get("value")
        target = {"query": query, "path": path_parameters, "header": headers}.get(location)
        if target is None:
            raise ValueError("Candidate uses an unsupported parameter location.")
        target[name] = str(value) if location in {"path", "header"} else value
    elif "remove_property" in mutation:
        name = mutation["remove_property"]
        if not isinstance(body, dict) or name not in body:
            raise ValueError(f"Provide a baseline JSON body containing '{name}'.")
        body.pop(name)
    elif mutation:
        name, value = next(iter(mutation.items()))
        parameter = next(
            (item for item in operation.get("parameters", []) if item.get("name") == name), None
        )
        location = parameter.get("in") if parameter else None
        target = {"query": query, "path": path_parameters, "header": headers}.get(location)
        if target is not None:
            target[name] = str(value) if location in {"path", "header"} else value
        elif isinstance(body, dict):
            body[name] = value
        else:
            raise ValueError("Provide baseline request values for this candidate.")

    path = operation["path"]
    for name, value in path_parameters.items():
        path = path.replace("{" + name + "}", quote(value, safe=""))
    if "{" in path or "}" in path:
        raise ValueError("Provide all path parameters for this operation.")
    base_url = config["base_url"].rstrip("/")
    url = base_url + "/" + path.lstrip("/")
    if query:
        url += "?" + urlencode(query, doseq=True)
    if len(url) > 4096:
        raise ValueError("Generated request URL exceeds the 4096 character limit.")
    if body is not None and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json"
    body_text = json.dumps(body, separators=(",", ":")) if body is not None else None
    if body_text is not None and len(body_text.encode("utf-8")) > 1_000_000:
        raise ValueError("Generated request body exceeds the 1 MB limit.")
    return {"method": operation["method"], "url": url, "headers": headers, "body": body_text}


def _environment_values(db: Session, campaign: CampaignRecord) -> dict[str, str]:
    environment_id = campaign.configuration.get("environment_id")
    if not environment_id:
        return {}
    environment = db.scalar(
        select(Environment).where(
            Environment.id == UUID(environment_id),
            Environment.project_id == campaign.project_id,
        )
    )
    if environment is None:
        raise ValueError("The selected environment is no longer available.")
    if not environment.secrets_migrated:
        encrypted = encrypt_environment_values(environment.variables)
        environment.secret_variables = {**environment.secret_variables, **encrypted}
        environment.variables = {}
        environment.secrets_migrated = True
        db.commit()
    try:
        return {
            **environment.variables,
            **decrypt_environment_values(environment.secret_variables),
        }
    except SecretStorageError as exc:
        raise ValueError(
            "Environment secrets could not be loaded; check the encryption key."
        ) from exc


def _resolve_request_templates(
    request: dict[str, Any], variables: dict[str, str]
) -> dict[str, Any]:
    def interpolate(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise ValueError(f"Environment variable '{name}' is not defined.")
            return variables[name]

        resolved = _TEMPLATE.sub(replace, value)
        if "{{" in resolved or "}}" in resolved:
            raise ValueError("An environment template variable could not be resolved.")
        return resolved

    return {
        **request,
        "url": interpolate(request["url"]),
        "headers": {key: interpolate(value) for key, value in request["headers"].items()},
        "body": interpolate(request["body"]) if request["body"] is not None else None,
    }


def _safe_execution_result(record: ExecutionRecord) -> dict[str, Any]:
    return {
        "outcome": record.outcome,
        "status_code": record.status_code,
        "duration_ms": record.duration_ms,
        "response_bytes": record.response_size_bytes,
        "origin": record.request_snapshot.get("origin"),
        "error": record.error_summary,
    }


async def process_campaign(db: Session, worker_id: str) -> bool:
    """Claim and process at most one durable campaign job."""
    now = datetime.now(UTC)
    job = db.scalar(
        select(CampaignJobRecord)
        .where(
            or_(
                (CampaignJobRecord.state == "queued") & (CampaignJobRecord.available_at <= now),
                (CampaignJobRecord.state == "leased") & (CampaignJobRecord.lease_expires_at <= now),
            )
        )
        .order_by(CampaignJobRecord.available_at, CampaignJobRecord.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return False
    campaign = db.get(CampaignRecord, job.campaign_id)
    if campaign is None or campaign.state in TERMINAL_STATES:
        job.state = "cancelled" if campaign and campaign.state == "cancelled" else "completed"
        db.commit()
        return True
    job.state = "leased"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    job.attempt_count += 1
    if campaign.started_at is None:
        campaign.started_at = now
        campaign.state = "running"
        append_event(db, campaign.id, "campaign_started", {})
    interrupted = list(
        db.scalars(
            select(TestCaseRecord).where(
                TestCaseRecord.campaign_id == campaign.id,
                TestCaseRecord.state == "running",
            )
        )
    )
    for case in interrupted:
        case.state = "inconclusive"
        case.result = {"outcome": "worker_interrupted_after_dispatch"}
        append_event(db, campaign.id, "test_inconclusive", {"test_case_id": str(case.id)})
    db.commit()

    cases = list(
        db.scalars(
            select(TestCaseRecord)
            .where(TestCaseRecord.campaign_id == campaign.id, TestCaseRecord.state == "queued")
            .order_by(TestCaseRecord.created_at, TestCaseRecord.id)
        )
    )
    started_at = campaign.started_at or now
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    executions = (
        db.scalar(
            select(func.count(ExecutionRecord.id)).where(ExecutionRecord.campaign_id == campaign.id)
        )
        or 0
    )
    iterations = (
        db.scalar(
            select(func.count(TestCaseRecord.id)).where(
                TestCaseRecord.campaign_id == campaign.id,
                TestCaseRecord.state.in_(["completed", "skipped", "inconclusive"]),
            )
        )
        or 0
    )
    budget_exhausted = False
    for case in cases:
        db.refresh(campaign)
        if campaign.cancel_requested_at is not None or campaign.state == "cancelled":
            case.state = "skipped"
            case.result = {"outcome": "cancelled_before_execution"}
            db.commit()
            continue
        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        if (
            executions >= campaign.budget_max_executions
            or iterations >= campaign.budget_max_iterations
            or elapsed >= campaign.budget_max_duration_seconds
        ):
            case.state = "skipped"
            case.result = {"outcome": "budget_exhausted"}
            budget_exhausted = True
            db.commit()
            continue
        iterations += 1
        try:
            request = _request_for_case(case, campaign.configuration)
            variables = _environment_values(db, campaign)
            if campaign.configuration.get("base_url"):
                variables["baseUrl"] = campaign.configuration["base_url"]
            request = _resolve_request_templates(request, variables)
        except (KeyError, TypeError, ValueError) as exc:
            case.state = "skipped"
            case.result = {"outcome": "missing_baseline", "message": str(exc)[:240]}
            append_event(db, campaign.id, "test_skipped", {"test_case_id": str(case.id)})
            db.commit()
            continue

        # Commit the started marker before network I/O; a reclaimed job never blindly repeats it.
        case.state = "running"
        job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
        db.commit()
        started = datetime.now(UTC)
        snapshot: dict[str, Any] = {
            "method": request["method"],
            "origin": "blocked",
            "candidate_id": case.candidate_key,
        }
        try:
            result = await execute_request(
                **request,
                confirm_unsafe=campaign.configuration.get("confirm_unsafe", False),
            )
            snapshot["origin"] = result["origin"]
            outcome, status_code = result["outcome"], result["status_code"]
            duration_ms, response_size = result["elapsed_ms"], result["response_bytes"]
            response_headers, error = result["headers"], None
        except ExecutionError as exc:
            outcome, status_code = exc.outcome, None
            duration_ms, response_size, response_headers, error = None, None, {}, str(exc)[:500]
        record = ExecutionRecord(
            project_id=campaign.project_id,
            campaign_id=campaign.id,
            test_case_id=case.id,
            outcome=outcome,
            request_snapshot=snapshot,
            status_code=status_code,
            duration_ms=duration_ms,
            response_headers=response_headers,
            response_size_bytes=response_size,
            started_at=started,
            completed_at=datetime.now(UTC),
            error_summary=error,
        )
        db.add(record)
        db.flush()
        case.execution_id = record.id
        case.state = "completed"
        case.result = {
            "outcome": outcome,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_bytes": response_size,
            "origin": snapshot["origin"],
            "error": error,
        }
        executions += 1
        append_event(
            db,
            campaign.id,
            "test_completed",
            {"test_case_id": str(case.id), "outcome": outcome, "status_code": status_code},
        )
        db.commit()

    db.refresh(campaign)
    db.refresh(job)
    if campaign.state not in TERMINAL_STATES:
        if budget_exhausted:
            campaign.failure_code = "budget_exhausted"
        campaign.state = "cancelled" if campaign.cancel_requested_at else "completed"
        campaign.completed_at = datetime.now(UTC)
        job.state = "cancelled" if campaign.state == "cancelled" else "completed"
        append_event(
            db,
            campaign.id,
            "campaign_cancelled" if campaign.state == "cancelled" else "campaign_completed",
            {"termination_reason": campaign.failure_code},
        )
    job.lease_owner = None
    job.lease_expires_at = None
    db.commit()
    return True


def campaign_event_read(event: CampaignEventRecord) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "sequence_number": event.sequence_number,
        "event_type": event.event_type,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }
