"""Owner-checked experiment creation, history, and shared metric aggregation."""

from time import perf_counter
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_user
from app.api.campaigns.router import _operation_assertions, _operation_case_values, append_event
from app.api.experiments.schemas import (
    ExperimentComparisonRead,
    ExperimentCreate,
    ExperimentListRead,
    ExperimentRead,
    ExperimentRunRead,
)
from app.db.session import get_db
from app.models.api_specification import APIOperation, APISpecification, KnowledgeFact
from app.models.campaign import Campaign, CampaignJob, TestCase
from app.models.environment import Environment
from app.models.execution import Execution
from app.models.experiment import Experiment, ExperimentRun
from app.models.finding import Finding
from app.models.health_check import AssertionResult
from app.models.project import Project
from app.models.user import User
from app.modules.api_understanding import normalized_operation_from_document
from app.modules.test_generation import GenerationApproach, generate_for_approach
from app.modules.test_generation.llm_assisted import PROMPT_VERSION

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "NOT_FOUND", "message": "Experiment not found."}
    )


def _experiment_state(states: list[str]) -> str:
    if not states:
        return "failed"
    if all(state == "completed" for state in states):
        return "completed"
    if all(state == "cancelled" for state in states):
        return "cancelled"
    if any(state == "running" for state in states):
        return "running"
    if any(state == "queued" for state in states):
        return "queued"
    if any(state == "failed" for state in states):
        return "partial" if any(state == "completed" for state in states) else "failed"
    return "partial"


def _experiment_read(db: Session, row: Experiment) -> ExperimentRead:
    results = db.execute(
        select(ExperimentRun, Campaign)
        .join(Campaign, Campaign.id == ExperimentRun.campaign_id)
        .where(ExperimentRun.experiment_id == row.id)
        .order_by(ExperimentRun.created_at, ExperimentRun.id)
    ).all()
    runs: list[ExperimentRunRead] = []
    states: list[str] = []
    for run, campaign in results:
        states.append(campaign.state)
        generation_metadata = dict(run.generation_metadata)
        llm_status = generation_metadata.get("llm_status")
        warning = generation_metadata.get("warning")
        legacy_attempted = llm_status == "succeeded" or (
            llm_status == "failed"
            and isinstance(warning, str)
            and warning.startswith("LLM candidate generation failed:")
        )
        generation_metadata.setdefault("llm_request_attempted", legacy_attempted)
        generation_metadata.setdefault(
            "semantic_facts_supplied_to_model",
            run.approach == GenerationApproach.SEMANTIC_ASSISTED.value
            and legacy_attempted
            and int(generation_metadata.get("semantic_fact_count", 0)) > 0,
        )
        generation_metadata.setdefault("rejected_candidates", [])
        generation_metadata.setdefault("rejected_candidate_count", 0)
        generation_metadata.setdefault(
            "requested_llm_provider", row.configuration.get("llm_provider")
        )
        generation_metadata.setdefault("requested_llm_model", row.configuration.get("llm_model"))
        candidates = (
            db.scalar(
                select(func.count())
                .select_from(TestCase)
                .where(TestCase.campaign_id == campaign.id)
            )
            or 0
        )
        executions = (
            db.scalar(
                select(func.count())
                .select_from(Execution)
                .where(Execution.campaign_id == campaign.id)
            )
            or 0
        )
        runs.append(
            ExperimentRunRead(
                id=run.id,
                campaign_id=campaign.id,
                approach=GenerationApproach(run.approach),
                state=campaign.state,
                configuration=run.configuration,
                generation_metadata=generation_metadata,
                candidate_count=candidates,
                execution_count=executions,
            )
        )
    return ExperimentRead(
        id=row.id,
        project_id=row.project_id,
        specification_id=row.specification_id,
        name=row.name,
        configuration=row.configuration,
        state=_experiment_state(states),
        created_at=row.created_at,
        updated_at=row.updated_at,
        runs=runs,
    )


def _owned_experiment(db: Session, experiment_id: UUID, user_id: UUID) -> Experiment:
    result = db.scalar(
        select(Experiment)
        .join(Project, Project.id == Experiment.project_id)
        .where(
            Experiment.id == experiment_id,
            Project.owner_user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if result is None:
        raise _not_found()
    return result


def _metric(value: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {"value": value, "unavailable_reason": reason}


def _campaign_metrics(db: Session, experiment: Experiment, run: ExperimentRun) -> dict[str, Any]:
    campaign_id = run.campaign_id
    candidates = db.scalars(select(TestCase).where(TestCase.campaign_id == campaign_id)).all()
    executions = db.scalars(select(Execution).where(Execution.campaign_id == campaign_id)).all()
    executed_test_ids = {item.test_case_id for item in executions if item.test_case_id is not None}
    exercised_operations = {
        case.operation_id
        for case in candidates
        if case.id in executed_test_ids and case.operation_id is not None
    }
    selected_operation_ids = experiment.configuration.get("operation_ids", [])
    selected_operation_count = len(selected_operation_ids)
    completed_execution_ids = {item.id for item in executions if item.status == "completed"}
    error_count = sum(item.status != "completed" for item in executions)
    asserted_execution_ids = set(
        db.scalars(
            select(AssertionResult.execution_id)
            .join(Execution, Execution.id == AssertionResult.execution_id)
            .where(Execution.campaign_id == campaign_id)
            .distinct()
        ).all()
    )
    failed_assertion_execution_ids = set(
        db.scalars(
            select(Execution.id)
            .join(AssertionResult, AssertionResult.execution_id == Execution.id)
            .where(
                Execution.campaign_id == campaign_id,
                AssertionResult.passed.is_(False),
            )
        ).all()
    )
    pass_count = len(
        (completed_execution_ids & asserted_execution_ids) - failed_assertion_execution_ids
    )
    fail_count = len(completed_execution_ids & failed_assertion_execution_ids)
    inconclusive_count = len(completed_execution_ids - asserted_execution_ids)
    finding_keys = set(
        db.scalars(
            select(Finding.finding_key).where(
                Finding.campaign_id == campaign_id,
                Finding.user_status == "confirmed",
            )
        ).all()
    )
    duration_ms = sum(item.duration_ms or 0 for item in executions)
    executed_count = len(executions)
    confirmed_count = len(finding_keys)
    generated_count = run.generation_metadata.get("generated_candidate_count")
    persisted_count = len(candidates)
    llm_status = run.generation_metadata.get("llm_status")
    stored_valid_count = run.generation_metadata.get("valid_candidate_count")
    llm_was_used = bool(run.generation_metadata.get("llm_request_attempted")) or (
        llm_status in {"succeeded", "empty", "failed"}
        and run.generation_metadata.get("mode") != "deterministic_fallback"
    )
    valid_candidate_count = int(
        stored_valid_count
        if stored_valid_count is not None
        else 0
        if llm_status == "failed" or not llm_was_used
        else generated_count or persisted_count
    )
    rejected_candidate_count = int(run.generation_metadata.get("rejected_candidate_count", 0))

    return {
        "candidate_validity_rate": _metric(
            round(valid_candidate_count / (valid_candidate_count + rejected_candidate_count), 4)
            if valid_candidate_count + rejected_candidate_count and llm_was_used
            else None,
            None
            if valid_candidate_count + rejected_candidate_count
            else (
                "LLM generation failed before any candidate proposal could be validated."
                if llm_status == "failed"
                else "LLM generation was not used for this approach."
                if not llm_was_used
                else "No generated or rejected candidate proposals were recorded."
            ),
        ),
        "unique_candidate_count": _metric(persisted_count),
        "generated_candidate_count": _metric(generated_count),
        "endpoint_coverage": _metric(
            round(len(exercised_operations) / selected_operation_count, 4)
            if selected_operation_count
            else None,
            None if selected_operation_count else "No selected operations were recorded.",
        ),
        "constraint_coverage": _metric(
            None,
            "Executed cases do not yet record stable constraint identifiers.",
        ),
        "execution_counts": {
            "passed": pass_count,
            "failed_assertions": fail_count,
            "errors": error_count,
            "inconclusive": inconclusive_count,
            "executed": executed_count,
        },
        "confirmed_defect_count": _metric(confirmed_count),
        "false_positive_rate": _metric(None, "No experiment ground-truth labels are recorded."),
        "requests_per_confirmed_defect": _metric(
            round(executed_count / confirmed_count, 4) if confirmed_count else None,
            None if confirmed_count else "No manually confirmed defect is recorded.",
        ),
        "time_to_first_confirmed_defect_ms": _metric(
            None,
            "Triage confirmation timestamps are not retained as an immutable event.",
        ),
        "generation_duration_ms": _metric(run.generation_metadata.get("generation_duration_ms")),
        "execution_duration_ms": _metric(duration_ms),
        "llm_token_usage": _metric(
            run.generation_metadata.get("llm_token_usage"),
            (
                "LLM generation failed before token usage was returned."
                if run.generation_metadata.get("llm_status") == "failed"
                else "LLM was not used for this approach."
                if run.generation_metadata.get("llm_status")
                in {"not_used", "disabled", "not_configured"}
                else "Provider did not return complete token usage for this run."
            )
            if run.generation_metadata.get("llm_token_usage") is None
            else None,
        ),
        "estimated_provider_cost": _metric(
            None,
            "LLM generation failed before provider usage was returned."
            if llm_status == "failed"
            else "LLM was not used for this approach."
            if llm_status in {"not_used", "disabled", "not_configured"}
            else "Provider pricing is not maintained, so cost cannot be estimated.",
        ),
        "diagnosis_accuracy": _metric(None, "No ground-truth failure labels are recorded."),
        "reproducibility_rate": _metric(
            None, "Repeat trials are not configured for this experiment."
        ),
    }


@router.post(
    "/projects/{project_id}/experiments",
    response_model=ExperimentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_experiment(
    project_id: UUID,
    payload: ExperimentCreate,
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
) -> ExperimentRead:
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
    operation_rows = list(
        db.execute(
            select(APIOperation, APISpecification)
            .join(APISpecification, APISpecification.id == APIOperation.specification_id)
            .where(
                APIOperation.id.in_(payload.operation_ids),
                APISpecification.project_id == project_id,
            )
            .order_by(APIOperation.operation_key)
        ).all()
    )
    if len(operation_rows) != len(payload.operation_ids):
        raise HTTPException(status_code=422, detail="Every operation must belong to this project.")
    specification_ids = {specification.id for _, specification in operation_rows}
    if len(specification_ids) != 1:
        raise HTTPException(
            status_code=422,
            detail="An experiment must use operations from one specification version.",
        )
    environment = db.scalar(
        select(Environment).where(
            Environment.id == payload.environment_id,
            Environment.project_id == project_id,
            Environment.base_url.is_not(None),
        )
    )
    if environment is None:
        raise HTTPException(
            status_code=422, detail="Environment must belong to the project and define a base URL."
        )

    operation_ids = [str(item) for item in payload.operation_ids]
    specification = operation_rows[0][1]
    configuration = {
        "operation_ids": operation_ids,
        "environment_id": str(environment.id),
        "approaches": [approach.value for approach in payload.approaches],
        "categories": [category.value for category in payload.categories],
        "use_llm": payload.use_llm,
        "llm_provider": payload.llm_provider,
        "llm_model": payload.llm_model,
        "budgets": {
            "max_executions_per_approach": payload.max_executions,
            "max_iterations_per_approach": payload.max_iterations,
            "max_duration_seconds_per_approach": payload.max_duration_seconds,
        },
        "specification_sha256": specification.content_sha256,
        "candidate_deduplication_policy": "stable_candidate_id_v1",
        "assertion_policy": "openapi_success_response_schema_v1",
        "ground_truth": "not_configured",
        "state_reset": "not_configured; target state is not reset between approach runs",
    }
    experiment = Experiment(
        project_id=project_id,
        created_by_user_id=current_user.id,
        specification_id=specification.id,
        name=payload.name,
        configuration=configuration,
    )
    db.add(experiment)
    db.flush()

    operation_uuid_set = set(payload.operation_ids)
    fact_rows = db.scalars(
        select(KnowledgeFact).where(KnowledgeFact.operation_id.in_(operation_uuid_set))
    ).all()
    facts_by_operation: dict[str, list[dict[str, Any]]] = {}
    operation_id_to_key: dict[UUID, str] = {}
    normalized_by_id = {}
    for operation_row, _ in operation_rows:
        normalized = normalized_operation_from_document(operation_row.operation_document)
        operation_id_to_key[operation_row.id] = normalized.operation_key
        normalized_by_id[operation_row.id] = normalized
    for fact in fact_rows:
        if fact.operation_id is None:
            continue
        operation_key = operation_id_to_key.get(fact.operation_id)
        if operation_key is None:
            continue
        facts_by_operation.setdefault(operation_key, []).append(
            {
                "fact_key": str(fact.id),
                "fact_type": fact.fact_type,
                "fact_value": fact.fact_value,
                "provenance": fact.provenance,
                "source_ref": fact.source_ref,
            }
        )

    for approach in payload.approaches:
        normalized_operations = tuple(
            normalized_by_id[operation_id] for operation_id in payload.operation_ids
        )
        generation_started = perf_counter()
        generation = generate_for_approach(
            approach,
            normalized_operations,
            semantic_facts_by_operation=facts_by_operation,
            allow_llm=payload.use_llm,
            llm_provider_name=payload.llm_provider,
            llm_model_name=payload.llm_model,
        )
        generation_duration_ms = round((perf_counter() - generation_started) * 1000)
        candidates_by_operation: dict[str, list[Any]] = {}
        for candidate in generation.candidates:
            if candidate.category in payload.categories:
                candidates_by_operation.setdefault(candidate.operation_key, []).append(candidate)
        cases: list[TestCase] = []
        for operation_row, operation_specification in operation_rows:
            normalized = normalized_by_id[operation_row.id]
            servers = operation_specification.spec_document.get("servers", [])
            server_path = ""
            if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
                server_path = urlsplit(servers[0]["url"]).path.rstrip("/")
            for candidate in candidates_by_operation.get(normalized.operation_key, []):
                parameters = _operation_case_values(normalized, candidate)
                if parameters is None:
                    continue
                if candidate.title == "Baseline request" and normalized.request_body_schema:
                    continue
                cases.append(
                    TestCase(
                        project_id=project_id,
                        operation_id=operation_row.id,
                        candidate_key=f"{operation_row.id}:{candidate.candidate_id}",
                        category=candidate.category.value,
                        title=candidate.title[:200],
                        description=candidate.rationale[:2000],
                        request_override={
                            "source": "openapi_candidate",
                            "candidate_id": candidate.candidate_id,
                            "operation_key": normalized.operation_key,
                            "method": candidate.method,
                            "path_template": candidate.path,
                            "server_path": server_path,
                            "parameters": parameters,
                            "body": candidate.body,
                        },
                        expected_behavior=(
                            _operation_assertions(normalized)
                            if candidate.category.value in {"positive", "schema"}
                            else None
                        ),
                        generation_provenance=(
                            "EXTRACTED"
                            if generation.generation_mode
                            in {"deterministic_pool", "deterministic_fallback"}
                            else "INFERRED"
                        ),
                    )
                )
        if not cases:
            raise HTTPException(
                status_code=422,
                detail=f"Approach {approach.value} produced no executable test cases.",
            )
        case_limit = min(payload.max_iterations, payload.max_executions, len(cases))
        campaign = Campaign(
            project_id=project_id,
            created_by_user_id=current_user.id,
            name=f"{payload.name} · {approach.value}"[:160],
            state="queued",
            configuration={
                "input_type": "openapi_operations",
                "operation_ids": operation_ids,
                "environment_id": str(environment.id),
                "selected_categories": [category.value for category in payload.categories],
                "approach": approach.value,
                "generation_policy_version": generation.generation_policy_version,
            },
            budget_max_executions=payload.max_executions,
            budget_max_iterations=payload.max_iterations,
            budget_max_duration_seconds=payload.max_duration_seconds,
        )
        db.add(campaign)
        db.flush()
        for case in cases[:case_limit]:
            case.campaign_id = campaign.id
            db.add(case)
        db.add(CampaignJob(campaign_id=campaign.id, state="queued"))
        append_event(
            db,
            campaign.id,
            "campaign_queued",
            {
                "experiment_id": str(experiment.id),
                "approach": approach.value,
                "test_count": case_limit,
                "budgets": configuration["budgets"],
            },
        )
        db.add(
            ExperimentRun(
                experiment_id=experiment.id,
                campaign_id=campaign.id,
                approach=approach.value,
                configuration={
                    "approach": approach.value,
                    "operation_ids": operation_ids,
                    "categories": configuration["categories"],
                    "budgets": configuration["budgets"],
                    "use_llm": payload.use_llm,
                },
                generation_metadata={
                    "policy_version": generation.generation_policy_version,
                    "prompt_version": (
                        PROMPT_VERSION
                        if approach
                        in {GenerationApproach.LLM_BASELINE, GenerationApproach.SEMANTIC_ASSISTED}
                        else None
                    ),
                    "mode": generation.generation_mode,
                    "llm_status": generation.llm_status,
                    "warning": generation.warning,
                    "semantic_fact_count": generation.semantic_fact_count,
                    "semantic_facts_supplied_to_model": generation.llm_request_attempted
                    and approach is GenerationApproach.SEMANTIC_ASSISTED,
                    "llm_request_attempted": generation.llm_request_attempted,
                    "llm_provider": generation.llm_provider,
                    "llm_model": generation.llm_model,
                    "llm_token_usage": generation.llm_token_usage,
                    "generated_candidate_count": len(generation.candidates),
                    "persisted_candidate_count": case_limit,
                    "generation_duration_ms": generation_duration_ms,
                    "valid_candidate_count": (
                        generation.valid_candidate_count
                        if generation.valid_candidate_count is not None
                        else len(generation.candidates)
                    ),
                    "rejected_candidate_count": sum(
                        item.get("kind") == "candidate" for item in generation.rejected_candidates
                    ),
                    "rejected_candidates": list(generation.rejected_candidates),
                    "requested_llm_provider": payload.llm_provider,
                    "requested_llm_model": payload.llm_model,
                },
            )
        )
    db.commit()
    db.refresh(experiment)
    response.headers["Location"] = f"/api/v1/experiments/{experiment.id}"
    return _experiment_read(db, experiment)


@router.get("/projects/{project_id}/experiments", response_model=ExperimentListRead)
def list_experiments(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperimentListRead:
    owned = db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.owner_user_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if owned is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."}
        )
    total = (
        db.scalar(
            select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id)
        )
        or 0
    )
    rows = db.scalars(
        select(Experiment)
        .where(Experiment.project_id == project_id)
        .order_by(Experiment.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExperimentListRead(
        items=[_experiment_read(db, row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(experiment_id: UUID, db: DbSession, current_user: CurrentUser) -> ExperimentRead:
    return _experiment_read(db, _owned_experiment(db, experiment_id, current_user.id))


@router.get("/experiments/{experiment_id}/comparison", response_model=ExperimentComparisonRead)
def compare_experiment(
    experiment_id: UUID, db: DbSession, current_user: CurrentUser
) -> ExperimentComparisonRead:
    experiment = _owned_experiment(db, experiment_id, current_user.id)
    runs = db.scalars(
        select(ExperimentRun)
        .where(ExperimentRun.experiment_id == experiment.id)
        .order_by(ExperimentRun.created_at, ExperimentRun.id)
    ).all()
    return ExperimentComparisonRead(
        experiment=_experiment_read(db, experiment),
        metrics_by_approach={run.approach: _campaign_metrics(db, experiment, run) for run in runs},
    )
