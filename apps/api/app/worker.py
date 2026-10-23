"""Separate durable campaign worker process.

Run with ``python -m app.worker``. Claims are transactional and expired leases
are recovered conservatively: a started test with no recorded execution is
marked uncertain and never sent to the target again.
"""

import json
import logging
import os
import re
import socket
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.campaign import Campaign, CampaignEvent, CampaignJob, TestCase
from app.models.execution import Execution
from app.models.finding import EvidenceReference, Finding
from app.models.health_check import AssertionResult
from app.models.saved_request import SavedRequest
from app.modules.adaptive import (
    AdaptiveScoringConfig,
    CandidateSignals,
    select_next_candidates,
)
from app.modules.execution.service import execute_request_definition, execute_saved_request
from app.modules.findings.service import is_sensitive_target
from app.modules.test_generation import CandidateCategory, TestCandidate

logger = logging.getLogger("intelapi.campaign_worker")
LEASE_SECONDS = 60
POLL_SECONDS = 2


def _event(db: Session, campaign_id: UUID, event_type: str, payload: dict[str, object]) -> None:
    sequence = (
        db.scalar(
            select(func.max(CampaignEvent.sequence_number)).where(
                CampaignEvent.campaign_id == campaign_id
            )
        )
        or 0
    )
    db.add(
        CampaignEvent(
            campaign_id=campaign_id,
            sequence_number=sequence + 1,
            event_type=event_type,
            payload=payload,
        )
    )


def claim_job(worker_id: str) -> UUID | None:
    now = datetime.now(UTC)
    with SessionLocal.begin() as db:
        job = db.scalar(
            select(CampaignJob)
            .join(Campaign)
            .where(
                Campaign.state.in_(["queued", "running"]),
                or_(
                    (CampaignJob.state == "queued") & (CampaignJob.available_at <= now),
                    (CampaignJob.state == "leased") & (CampaignJob.lease_expires_at < now),
                ),
            )
            .order_by(CampaignJob.available_at, CampaignJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        campaign = db.scalar(
            select(Campaign).where(Campaign.id == job.campaign_id).with_for_update()
        )
        if campaign is None or campaign.state in {"completed", "failed", "cancelled"}:
            job.state = "cancelled"
            return None
        job.state = "leased"
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        job.attempt_count += 1
        if campaign.state == "queued":
            campaign.state = "running"
            campaign.started_at = now
            _event(db, campaign.id, "campaign_started", {"worker_id": worker_id})
        return campaign.id


def _set_terminal(
    db: Session,
    campaign: Campaign,
    job: CampaignJob,
    state: str,
    event_type: str,
    payload: dict[str, object] | None = None,
) -> None:
    now = datetime.now(UTC)
    campaign.state = state
    campaign.completed_at = now
    job.state = (
        "completed" if state == "completed" else "cancelled" if state == "cancelled" else "failed"
    )
    job.lease_owner = None
    job.lease_expires_at = None
    _event(db, campaign.id, event_type, payload or {})


def _execute_case(db: Session, campaign: Campaign, test_case: TestCase) -> Execution:
    override = test_case.request_override
    environment_id = campaign.configuration.get("environment_id")
    if override.get("source") != "openapi_candidate":
        request_id = UUID(override["saved_request_id"])
        request = db.scalar(
            select(SavedRequest).where(
                SavedRequest.id == request_id, SavedRequest.project_id == campaign.project_id
            )
        )
        if request is None:
            raise RuntimeError("A campaign request was removed before execution.")
        return execute_saved_request(
            db,
            request,
            campaign.created_by_user_id,
            UUID(environment_id) if environment_id else None,
            10,
            campaign.id,
            test_case.id,
        )
    environment_id = UUID(environment_id)
    parameters = override.get("parameters") or {}
    path_values = parameters.get("path") or {}
    path = re.sub(
        r"\{([^{}]+)\}",
        lambda match: quote(str(path_values[match.group(1)]), safe=""),
        override["path_template"],
    )
    path = f"{override.get('server_path', '').rstrip('/')}/{path.lstrip('/')}"
    return execute_request_definition(
        db,
        project_id=campaign.project_id,
        saved_request_id=None,
        owner_user_id=campaign.created_by_user_id,
        environment_override_id=environment_id,
        timeout_seconds=10,
        method=override["method"],
        url_template=path,
        headers=parameters.get("header") or {},
        query_params=parameters.get("query") or {},
        body=override.get("body"),
        body_type="json" if override.get("body") is not None else "none",
        campaign_id=campaign.id,
        test_case_id=test_case.id,
    )


def _json_path(value: object, target: str) -> tuple[bool, object]:
    parts = target.split(".") if target != "$" else []

    def walk(current: object, remaining: list[str]) -> tuple[bool, object]:
        if not remaining:
            return True, current
        part, tail = remaining[0], remaining[1:]
        if part.endswith("[]"):
            field = part[:-2]
            if not isinstance(current, dict) or not isinstance(current.get(field), list):
                return False, None
            items = current[field]
            if not tail:
                return True, items
            resolved = [walk(item, tail) for item in items]
            return bool(resolved) and all(found for found, _ in resolved), [
                item for _, item in resolved
            ]
        if isinstance(current, dict) and part in current:
            return walk(current[part], tail)
        if (
            isinstance(current, list)
            and part.endswith("]")
            and part.rsplit("[", 1)[-1][:-1].isdigit()
        ):
            index = int(part.rsplit("[", 1)[-1][:-1])
            return walk(current[index], tail) if index < len(current) else (False, None)
        return False, None

    return walk(value, parts)


def _evaluate_case(
    db: Session, campaign: Campaign, test_case: TestCase, execution: Execution
) -> None:
    expected = test_case.expected_behavior or {}
    assertions = list(expected.get("assertions", []))
    success_status_codes = expected.get("success_status_codes", [])
    if success_status_codes:
        assertions.insert(
            0,
            {
                "type": "status_code_set",
                "response_status_code": None,
                "target": "status",
                "expected": success_status_codes,
                "source_ref": None,
                "rationale": "OpenAPI declares the acceptable successful response statuses.",
            },
        )
    if execution.status != "completed" or not assertions:
        return
    try:
        response = json.loads(execution.response_body or "null")
    except (json.JSONDecodeError, TypeError):
        response = None
    for item in assertions:
        target = item.get("target", "")
        if (
            item.get("response_status_code") is not None
            and item.get("response_status_code") != execution.response_status_code
        ) or is_sensitive_target(target):
            continue
        assertion_type = item["type"]
        if assertion_type == "status_code":
            actual: object = execution.response_status_code
            passed = actual == item.get("expected")
        elif assertion_type == "status_code_set":
            actual = execution.response_status_code
            passed = actual in item.get("expected", [])
        else:
            exists, value = _json_path(response, target)
            if assertion_type == "required_property":
                actual, passed = exists, exists == item.get("expected")
            elif assertion_type == "property_type":
                type_names = {
                    dict: "object",
                    list: "array",
                    str: "string",
                    bool: "boolean",
                    int: "integer",
                    float: "number",
                    type(None): "null",
                }
                wildcard = target.endswith("[]") or "[]." in target
                values = value if wildcard and isinstance(value, list) else [value]
                actual = (
                    [type_names.get(type(entry), "unknown") for entry in values] if exists else None
                )
                passed = (
                    exists
                    and isinstance(actual, list)
                    and bool(actual)
                    and all(kind == item.get("expected") for kind in actual)
                )
                if isinstance(actual, list) and len(actual) == 1 and not wildcard:
                    actual = actual[0]
            else:
                continue
        result = AssertionResult(
            execution_id=execution.id,
            health_check_id=None,
            assertion_type=assertion_type,
            passed=bool(passed),
            expected=item.get("expected"),
            actual=actual,
            message=(
                "OpenAPI response assertion passed."
                if passed
                else "OpenAPI response assertion failed."
            )[:2000],
        )
        db.add(result)
        db.flush()
        if passed:
            continue
        from hashlib import sha256

        key = sha256(
            f"campaign:{campaign.id}:test:{test_case.id}:execution:{execution.id}:assertion:{result.id}".encode()
        ).hexdigest()
        finding = Finding(
            project_id=campaign.project_id,
            campaign_id=campaign.id,
            test_case_id=test_case.id,
            execution_id=execution.id,
            finding_key=key,
            title="OpenAPI response assertion mismatch",
            summary=(
                "The observed response did not match a declared OpenAPI response assertion. "
                "Human review is required."
            ),
            classification=(
                "schema_mismatch"
                if assertion_type in {"required_property", "property_type"}
                else "assertion_mismatch"
            ),
            machine_severity="medium",
            confidence=0.8,
            user_status="open",
        )
        db.add(finding)
        db.flush()
        db.add(
            EvidenceReference(
                project_id=campaign.project_id,
                finding_id=finding.id,
                execution_id=execution.id,
                assertion_result_id=result.id,
                specification_id=None,
                operation_id=test_case.operation_id,
                provenance="DECLARED",
                evidence_type="openapi_assertion",
                excerpt=(
                    f"{item.get('rationale', '')} Expected {item.get('expected')!r}; "
                    f"observed {actual!r}."
                )[:2000],
                evidence_metadata={
                    "assertion_type": assertion_type,
                    "target": target,
                    "source_ref": item.get("source_ref"),
                },
            )
        )


def _select_next_case(
    db: Session, campaign_id: UUID, pending: list[TestCase]
) -> tuple[TestCase, dict[str, object] | None]:
    campaign = db.get(Campaign, campaign_id)
    approach = campaign.configuration.get("approach") if campaign is not None else None
    openapi_cases = [
        case for case in pending if case.request_override.get("source") == "openapi_candidate"
    ]
    if not openapi_cases:
        return pending[0], None
    if approach in {"llm_baseline", "semantic_assisted"}:
        selected = min(openapi_cases, key=lambda case: (case.created_at, str(case.id)))
        return selected, {
            "policy_version": "fixed-generation-order-v1",
            "rationale": (
                "Baseline candidate order is fixed; prior execution feedback is not used "
                "for selection."
            ),
            "test_case_id": str(selected.id),
            "evidence_ids": [],
        }
    history = db.execute(
        select(
            TestCase.operation_id, TestCase.category, Execution.response_status_code, Execution.id
        )
        .join(Execution, Execution.test_case_id == TestCase.id)
        .where(TestCase.campaign_id == campaign_id)
    ).all()
    finding_case_ids = db.scalars(
        select(Finding.test_case_id).where(
            Finding.campaign_id == campaign_id, Finding.test_case_id.is_not(None)
        )
    ).all()
    seen_categories = {category for _, category, _, _ in history}
    operation_statuses: dict[UUID | None, set[int]] = {}
    operations_with_findings: set[UUID | None] = set()
    for operation_id, _, status_code, _ in history:
        if status_code is not None:
            operation_statuses.setdefault(operation_id, set()).add(status_code)
    for test_case_id in finding_case_ids:
        case = db.get(TestCase, test_case_id)
        if case is not None:
            operations_with_findings.add(case.operation_id)

    candidates: list[TestCandidate] = []
    signals: dict[str, CandidateSignals] = {}
    candidate_to_case: dict[str, TestCase] = {}
    for case in openapi_cases:
        override = case.request_override
        scorer_id = f"{case.operation_id}:{override['candidate_id']}"
        category = CandidateCategory(case.category)
        candidate = TestCandidate(
            candidate_id=scorer_id,
            operation_key=str(override.get("operation_key", case.operation_id)),
            category=category,
            title=case.title,
            method=override["method"],
            path=override["path_template"],
            parameters=override.get("parameters") or {},
            body=override.get("body"),
            rationale=case.description or "",
        )
        candidates.append(candidate)
        candidate_to_case[scorer_id] = case
        operation_history = [row for row in history if row[0] == case.operation_id]
        first_test = not operation_history
        signals[scorer_id] = CandidateSignals(
            candidate_id=scorer_id,
            unexpectedness=0.95 if case.operation_id in operations_with_findings else 0.0,
            novelty=0.8 if case.category not in seen_categories else 0.2,
            boundary_relevance=0.9 if category == CandidateCategory.BOUNDARY else 0.0,
            inconsistency=0.8 if len(operation_statuses.get(case.operation_id, set())) > 1 else 0.0,
            exploration_value=(1.0 if category == CandidateCategory.POSITIVE else 0.35)
            if first_test
            else (0.65 if case.category not in seen_categories else 0.25),
            cost_risk_penalty=(
                0.35 if candidate.method.upper() in {"POST", "PUT", "PATCH", "DELETE"} else 0.05
            ),
            evidence_ids=tuple(str(row[3]) for row in operation_history),
        )
    scoring_config = None
    if approach == "evidence_backed":
        scoring_config = AdaptiveScoringConfig(
            policy_version="evidence-coverage-v1",
            unexpectedness_weight=0.15,
            novelty_weight=0.35,
            boundary_relevance_weight=0.1,
            inconsistency_weight=0.05,
            exploration_value_weight=0.35,
            cost_risk_weight=0.25,
        )
    ranked = select_next_candidates(
        candidates,
        signals,
        limit=1,
        diversify=True,
        config=scoring_config or AdaptiveScoringConfig(),
    )
    if not ranked:
        return pending[0], None
    result = ranked[0]
    return candidate_to_case[result.candidate.candidate_id], {
        "score": result.score,
        "policy_version": result.policy_version,
        "rationale": result.rationale,
        "category": result.candidate.category.value,
        "test_case_id": str(candidate_to_case[result.candidate.candidate_id].id),
        "evidence_ids": list(result.evidence_ids),
    }


def process_campaign(campaign_id: UUID) -> None:
    with SessionLocal() as db:
        campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id))
        job = db.scalar(select(CampaignJob).where(CampaignJob.campaign_id == campaign_id))
        if campaign is None or job is None:
            return
        cases = db.scalars(
            select(TestCase)
            .where(TestCase.campaign_id == campaign_id)
            .order_by(TestCase.created_at, TestCase.id)
        ).all()

    pending_cases = list(cases)
    while pending_cases:
        with SessionLocal() as db:
            test_case, selection = _select_next_case(db, campaign_id, pending_cases)
        pending_cases.remove(test_case)
        with SessionLocal.begin() as db:
            campaign = db.scalar(
                select(Campaign).where(Campaign.id == campaign_id).with_for_update()
            )
            job = db.scalar(
                select(CampaignJob).where(CampaignJob.campaign_id == campaign_id).with_for_update()
            )
            if campaign is None or job is None:
                return
            if campaign.state in {"completed", "failed", "cancelled"}:
                return
            if campaign.cancel_requested_at is not None:
                _set_terminal(db, campaign, job, "cancelled", "campaign_cancelled", {})
                return
            now = datetime.now(UTC)
            if (
                campaign.started_at
                and (now - campaign.started_at).total_seconds()
                >= campaign.budget_max_duration_seconds
            ):
                _set_terminal(
                    db, campaign, job, "completed", "budget_exhausted", {"budget": "duration"}
                )
                return
            existing = db.scalar(select(Execution.id).where(Execution.test_case_id == test_case.id))
            if existing is not None:
                continue
            started_before = db.scalar(
                select(CampaignEvent.id).where(
                    CampaignEvent.campaign_id == campaign_id,
                    CampaignEvent.event_type == "test_execution_started",
                    CampaignEvent.payload["test_case_id"].astext == str(test_case.id),
                )
            )
            if started_before is not None:
                campaign.state = "failed"
                campaign.failure_code = "EXECUTION_OUTCOME_UNCERTAIN"
                campaign.failure_summary = (
                    "A target request may have been sent before the worker stopped; "
                    "it was not retried."
                )
                campaign.completed_at = now
                job.state = "failed"
                job.last_error_code = campaign.failure_code
                job.lease_owner = None
                job.lease_expires_at = None
                _event(
                    db,
                    campaign_id,
                    "execution_outcome_uncertain",
                    {"test_case_id": str(test_case.id)},
                )
                return
            if selection is not None:
                selection_event = (
                    "evidence_candidate_selected"
                    if campaign.configuration.get("approach") == "evidence_backed"
                    else "experiment_candidate_selected"
                    if campaign.configuration.get("approach")
                    in {"llm_baseline", "semantic_assisted"}
                    else "adaptive_candidate_selected"
                )
                _event(db, campaign_id, selection_event, selection)
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(Execution)
                    .where(Execution.campaign_id == campaign_id)
                )
                or 0
            )
            if count >= campaign.budget_max_executions:
                _set_terminal(
                    db, campaign, job, "completed", "budget_exhausted", {"budget": "executions"}
                )
                return
            job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
            _event(
                db,
                campaign_id,
                "test_execution_started",
                {"test_case_id": str(test_case.id)},
            )

        # The durable start event is committed before any outbound network call.
        try:
            with SessionLocal() as db:
                current_campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id))
                current_case = db.scalar(select(TestCase).where(TestCase.id == test_case.id))
                if current_campaign is None or current_case is None:
                    raise RuntimeError("Campaign test case disappeared before execution.")
                execution = _execute_case(db, current_campaign, current_case)
        except (HTTPException, RuntimeError) as exc:
            with SessionLocal.begin() as db:
                campaign = db.scalar(
                    select(Campaign).where(Campaign.id == campaign_id).with_for_update()
                )
                job = db.scalar(
                    select(CampaignJob)
                    .where(CampaignJob.campaign_id == campaign_id)
                    .with_for_update()
                )
                if campaign and job:
                    campaign.state = "failed"
                    campaign.failure_code = "CAMPAIGN_EXECUTION_FAILED"
                    campaign.failure_summary = str(exc)[:2000]
                    campaign.completed_at = datetime.now(UTC)
                    job.state = "failed"
                    job.last_error_code = campaign.failure_code
                    job.lease_owner = None
                    job.lease_expires_at = None
                    _event(db, campaign_id, "campaign_failed", {"code": campaign.failure_code})
            return

        with SessionLocal.begin() as db:
            campaign = db.scalar(
                select(Campaign).where(Campaign.id == campaign_id).with_for_update()
            )
            job = db.scalar(
                select(CampaignJob).where(CampaignJob.campaign_id == campaign_id).with_for_update()
            )
            if campaign is None or job is None:
                return
            current_case = db.scalar(select(TestCase).where(TestCase.id == test_case.id))
            current_execution = db.scalar(select(Execution).where(Execution.id == execution.id))
            if current_case is not None and current_execution is not None:
                _evaluate_case(db, campaign, current_case, current_execution)
            _event(
                db,
                campaign_id,
                "test_execution_completed",
                {
                    "test_case_id": str(test_case.id),
                    "execution_id": str(execution.id),
                    "execution_status": execution.status,
                    "response_status_code": execution.response_status_code,
                },
            )
            job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)

    with SessionLocal.begin() as db:
        campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update())
        job = db.scalar(
            select(CampaignJob).where(CampaignJob.campaign_id == campaign_id).with_for_update()
        )
        if campaign is None or job is None:
            return
        if campaign.cancel_requested_at is not None:
            _set_terminal(db, campaign, job, "cancelled", "campaign_cancelled", {})
        else:
            duration_expired = (
                campaign.started_at
                and (datetime.now(UTC) - campaign.started_at).total_seconds()
                >= campaign.budget_max_duration_seconds
            )
            budget_reason = (
                "duration"
                if duration_expired
                else "executions"
                if len(cases) >= campaign.budget_max_executions
                else "iterations"
                if len(cases) >= campaign.budget_max_iterations
                else None
            )
            _set_terminal(
                db,
                campaign,
                job,
                "completed",
                "budget_exhausted" if budget_reason else "campaign_completed",
                {"budget": budget_reason} if budget_reason else {"execution_count": len(cases)},
            )


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    logger.info("Campaign worker started")
    while True:
        try:
            campaign_id = claim_job(worker_id)
            if campaign_id is None:
                time.sleep(POLL_SECONDS)
            else:
                process_campaign(campaign_id)
        except Exception:
            logger.exception("Campaign worker iteration failed")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
