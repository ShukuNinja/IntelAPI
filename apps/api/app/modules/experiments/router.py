"""Persisted, reproducible experiment generation and execution endpoints."""

from __future__ import annotations

import json
import time
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ApiSpecification, ExecutionReportRecord, ExperimentRunRecord
from app.modules.api_understanding.service import generate_candidates
from app.modules.experiments.semantic import candidate_semantic_score, extract_semantic_facts
from app.modules.test_generation.router import (
    CandidateExecutionInput,
    _project,
    execute_candidate,
)

router = APIRouter(
    prefix="/projects/{project_id}/specifications/{specification_id}/experiments",
    tags=["experiments"],
)


class GenerateExperimentInput(BaseModel):
    approach: Literal["contract_baseline", "semantic_guided"]
    candidate_budget: int = Field(default=25, ge=1, le=100)


class OperationBaseline(BaseModel):
    path_parameters: dict[str, str] = Field(default_factory=dict)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict, max_length=100)
    body: dict[str, Any] | list[Any] | None = None
    expected_status_code: int | None = Field(default=None, ge=100, le=599)


class ExecuteExperimentInput(BaseModel):
    base_url: AnyHttpUrl
    baselines: dict[str, OperationBaseline] = Field(default_factory=dict)
    confirm_unsafe: bool = False
    execution_budget: int = Field(default=10, ge=1, le=20)


def _record_read(record: ExperimentRunRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "project_id": str(record.project_id),
        "specification_id": str(record.specification_id),
        "approach": record.approach,
        "status": record.status,
        "configuration": record.configuration,
        "result": record.result,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _all_candidates(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for operation in operations:
        for candidate in generate_candidates(operation, 100):
            rows.append(
                {
                    **candidate,
                    "operation_id": operation.get("id"),
                    "operation": {key: operation.get(key) for key in ("method", "path", "summary")},
                }
            )
    # IDs are stable for a given spec operation and mutation; guard against duplicate IDs.
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(row["id"], row)
    return list(unique.values())


def _candidate_field(candidate: dict[str, Any]) -> str:
    mutation = candidate.get("mutation", {})
    if "remove_property" in mutation:
        return str(mutation["remove_property"])
    for key in ("remove_parameter", "set_parameter"):
        if key in mutation:
            return str(mutation[key].get("name", ""))
    return str(next(iter(mutation), ""))


def _constraint_inventory(operations: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    measurable = {"minimum", "maxLength", "enum"}
    found: set[tuple[str, str, str]] = set()

    def visit(operation_id: str, schema: Any, field: str = "") -> None:
        if not isinstance(schema, dict):
            return
        for rule in measurable.intersection(schema):
            if field:
                found.add((operation_id, field, rule))
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for name, child in properties.items():
                visit(operation_id, child, str(name))

    for operation in operations:
        operation_id = str(operation.get("id"))
        for parameter in operation.get("parameters", []):
            if isinstance(parameter, dict):
                visit(operation_id, parameter.get("schema"), str(parameter.get("name", "")))
        request_body = operation.get("request_body", {})
        content = request_body.get("content", {}) if isinstance(request_body, dict) else {}
        media = content.get("application/json", {}) if isinstance(content, dict) else {}
        schema = media.get("schema", {}) if isinstance(media, dict) else {}
        visit(operation_id, schema)
    return found


def _covered_constraints(
    selected: list[dict[str, Any]], inventory: set[tuple[str, str, str]]
) -> set[tuple[str, str, str]]:
    supported_by_kind = {
        "parameter-minimum-boundary": {"minimum"},
        "body-minimum-boundary": {"minimum"},
        "parameter-length-boundary": {"maxLength"},
        "body-length-boundary": {"maxLength"},
        "parameter-enum-boundary": {"enum"},
        "body-enum-boundary": {"enum"},
    }
    return {
        atom
        for candidate in selected
        for atom in inventory
        if atom[0] == candidate.get("operation_id")
        and atom[1] == _candidate_field(candidate)
        and atom[2] in supported_by_kind.get(candidate.get("kind") or "", set())
    }


def _rank_contract(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "required-parameter-omitted": 0,
        "required-body-property-omitted": 0,
        "parameter-enum-boundary": 1,
        "parameter-minimum-boundary": 2,
        "parameter-length-boundary": 2,
    }
    return sorted(
        candidates, key=lambda c: (priority.get(c["kind"], 9), c["operation_id"], c["id"])
    )


def _select_semantic(
    candidates: list[dict[str, Any]], operations: list[dict[str, Any]], facts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    op_by_id = {op.get("id"): op for op in operations}
    for candidate in candidates:
        score, breakdown = candidate_semantic_score(
            candidate, op_by_id.get(candidate["operation_id"], {}), facts
        )
        candidate["score"] = round(score, 3)
        candidate["score_breakdown"] = breakdown
    # Greedy selection with operation diversity as the tie-breaker. Semantic terms change rank.
    return sorted(candidates, key=lambda c: (-c["score"], c["operation_id"], c["id"]))


@router.post("", status_code=201)
def create_experiment(
    project_id: UUID,
    specification_id: UUID,
    payload: GenerateExperimentInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = _project(db, project_id)
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id, ApiSpecification.project_id == project.id
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    operations = specification.normalized_operations
    start = time.perf_counter_ns()
    candidates = _all_candidates(operations)
    generation_ms = (time.perf_counter_ns() - start) / 1_000_000
    semantic_ms = None
    facts: list[dict[str, Any]] = []
    if payload.approach == "semantic_guided":
        start = time.perf_counter_ns()
        facts = extract_semantic_facts(operations)
        semantic_ms = (time.perf_counter_ns() - start) / 1_000_000
        ranked = _select_semantic(candidates, operations, facts)
    else:
        ranked = _rank_contract(candidates)
        for candidate in ranked:
            candidate["score"] = None
            candidate["score_breakdown"] = None
    selected = ranked[: payload.candidate_budget]
    measurable_constraints = _constraint_inventory(operations)
    covered_constraints = _covered_constraints(selected, measurable_constraints)
    operation_count = len(operations)
    selected_operations = {candidate["operation_id"] for candidate in selected}
    result = {
        "metric_definitions": {
            "selection_rate": "selected candidates / unique generated candidates",
            "operation_coverage": (
                "operations with at least one selected candidate / all imported operations"
            ),
            "constraint_coverage": (
                "supported minimum, maxLength, and enum constraints exercised by "
                "selected candidates / matching imported constraints; unavailable if none exist"
            ),
            "generation_duration_ms": (
                "wall-clock candidate generation time, excluding semantic extraction "
                "and network execution"
            ),
        },
        "metrics": {
            "generation_duration_ms": round(generation_ms, 3),
            "semantic_extraction_duration_ms": round(semantic_ms, 3)
            if semantic_ms is not None
            else None,
            "total_candidates_generated": len(candidates),
            "unique_candidates": len({candidate["id"] for candidate in candidates}),
            "candidates_selected": len(selected),
            "candidate_selection_rate": round(len(selected) / len(candidates), 4)
            if candidates
            else 0.0,
            "operations_covered": len(selected_operations),
            "operation_count": operation_count,
            "operation_coverage_percent": round(len(selected_operations) / operation_count * 100, 2)
            if operation_count
            else 0.0,
            "constraints_covered": len(covered_constraints) if measurable_constraints else None,
            "constraint_count": len(measurable_constraints) if measurable_constraints else None,
            "constraint_coverage_percent": round(
                len(covered_constraints) / len(measurable_constraints) * 100, 2
            )
            if measurable_constraints
            else None,
            "executions_completed": 0,
            "assertion_passes": 0,
            "assertion_failures": 0,
            "inconclusive_outcomes": 0,
            "execution_duration_ms": None,
            "known_seeded_defects_detected": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "detection_rate": None,
            "time_to_first_seeded_defect_ms": None,
        },
        "facts": facts,
        "selected_candidates": selected,
        "generated_candidates": ranked,
        "execution_results": [],
        "ground_truth": (
            {
                "available": True,
                "evaluated": False,
                "benchmark_id": specification.source_document["x-intelapi-benchmark"].get("id"),
                "seeded_defects": specification.source_document["x-intelapi-benchmark"].get(
                    "defects", []
                ),
            }
            if isinstance(specification.source_document.get("x-intelapi-benchmark"), dict)
            else {
                "available": False,
                "reason": "No seeded-defect benchmark is configured for this run.",
            }
        ),
    }
    record = ExperimentRunRecord(
        project_id=project.id,
        specification_id=specification.id,
        approach=payload.approach,
        status="generated",
        configuration={
            "candidate_budget": payload.candidate_budget,
            "selection_policy": "contract-priority-v1"
            if payload.approach == "contract_baseline"
            else "semantic-score-v1",
            "specification_hash": specification.content_hash,
        },
        result=result,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_read(record)


@router.get("")
def list_experiments(
    project_id: UUID,
    specification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    project = _project(db, project_id)
    records = db.scalars(
        select(ExperimentRunRecord)
        .where(
            ExperimentRunRecord.project_id == project.id,
            ExperimentRunRecord.specification_id == specification_id,
        )
        .order_by(ExperimentRunRecord.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(item.id),
            "approach": item.approach,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
            "metrics": item.result.get("metrics", {}),
        }
        for item in records
    ]


def _get_run(
    db: Session, project_id: UUID, specification_id: UUID, run_id: UUID
) -> ExperimentRunRecord:
    project = _project(db, project_id)
    record = db.scalar(
        select(ExperimentRunRecord).where(
            ExperimentRunRecord.id == run_id,
            ExperimentRunRecord.project_id == project.id,
            ExperimentRunRecord.specification_id == specification_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Experiment run not found.")
    return record


@router.get("/comparison")
def compare_experiments(
    project_id: UUID,
    specification_id: UUID,
    baseline_run_id: UUID,
    semantic_run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    baseline = _get_run(db, project_id, specification_id, baseline_run_id)
    semantic = _get_run(db, project_id, specification_id, semantic_run_id)
    if baseline.approach != "contract_baseline" or semantic.approach != "semantic_guided":
        raise HTTPException(
            status_code=422, detail="Choose one contract baseline and one semantic-guided run."
        )
    return {
        "baseline": _record_read(baseline),
        "semantic_guided": _record_read(semantic),
        "same_specification": baseline.specification_id == semantic.specification_id,
        "same_candidate_budget": baseline.configuration.get("candidate_budget")
        == semantic.configuration.get("candidate_budget"),
    }


@router.get("/comparison/export")
def export_comparison_static(
    project_id: UUID,
    specification_id: UUID,
    baseline_run_id: UUID,
    semantic_run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown"] = Query(default="json"),
) -> Response:
    comparison = compare_experiments(
        project_id, specification_id, baseline_run_id, semantic_run_id, db
    )
    if format == "json":
        body = json.dumps(comparison, ensure_ascii=False, indent=2)
        media_type = "application/json"
    else:
        metrics_a = comparison["baseline"]["result"]["metrics"]
        metrics_b = comparison["semantic_guided"]["result"]["metrics"]
        keys = sorted(set(metrics_a) | set(metrics_b))
        body = "\n".join(
            [
                "# IntelAPI experiment comparison",
                "",
                "| Metric | Approach A | Approach B |",
                "|---|---:|---:|",
            ]
            + [f"| {key} | {metrics_a.get(key)} | {metrics_b.get(key)} |" for key in keys]
        )
        media_type = "text/markdown; charset=utf-8"
    return Response(content=body, media_type=media_type)


@router.get("/{run_id}")
def get_experiment(
    project_id: UUID, specification_id: UUID, run_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    return _record_read(_get_run(db, project_id, specification_id, run_id))


@router.post("/{run_id}/execute")
async def execute_experiment(
    project_id: UUID,
    specification_id: UUID,
    run_id: UUID,
    payload: ExecuteExperimentInput,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    record = _get_run(db, project_id, specification_id, run_id)
    if record.status == "executed":
        raise HTTPException(
            status_code=409, detail="This experiment run has already been executed."
        )
    project = _project(db, project_id)
    specification = db.scalar(
        select(ApiSpecification).where(
            ApiSpecification.id == specification_id, ApiSpecification.project_id == project.id
        )
    )
    if specification is None:
        raise HTTPException(status_code=404, detail="Specification not found.")
    selected = record.result.get("selected_candidates", [])[: payload.execution_budget]
    base_url = str(payload.base_url).rstrip("/")
    start = time.perf_counter_ns()
    results = []
    benchmark_marker = specification.source_document.get("x-intelapi-benchmark")
    target_parts = urlsplit(base_url)
    if (
        target_parts.username
        or target_parts.password
        or target_parts.query
        or target_parts.fragment
    ):
        raise HTTPException(
            status_code=422,
            detail="Target base URL cannot include credentials, a query, or a fragment.",
        )
    if target_parts.scheme not in {"http", "https"} or not target_parts.hostname:
        raise HTTPException(
            status_code=422, detail="Target base URL must be an absolute HTTP or HTTPS URL."
        )
    benchmark_active = (
        isinstance(benchmark_marker, dict)
        and benchmark_marker.get("id") == "intelapi-seeded-v1"
        and target_parts.hostname in {"localhost", "127.0.0.1", "::1"}
        and target_parts.path.rstrip("/").endswith("/api/v1/research-benchmark")
    )
    for candidate in selected:
        operation_id = candidate.get("operation_id")
        baseline = payload.baselines.get(operation_id, OperationBaseline())
        operation = next(
            (
                item
                for item in specification.normalized_operations
                if item.get("id") == operation_id
            ),
            None,
        )
        if operation is None:
            results.append(
                {
                    "candidate_id": candidate.get("id"),
                    "outcome": "inconclusive",
                    "reason": "Operation no longer exists.",
                }
            )
            continue
        expected = baseline.expected_status_code
        if expected is None:
            responses = operation.get("responses", {})
            expected_key = next(
                (key for key in ("200", "201", "202", "204") if key in responses), None
            )
            expected = int(expected_key) if expected_key else None
        execution_payload = CandidateExecutionInput.model_validate(
            {
                "base_url": base_url,
                "path_parameters": baseline.path_parameters,
                "query_parameters": baseline.query_parameters,
                "headers": baseline.headers,
                "body": baseline.body,
                "expected_status_code": expected,
                "confirm_unsafe": payload.confirm_unsafe,
                "follow_up_budget": 0,
            }
        )
        try:
            output = await execute_candidate(
                project_id=project_id,
                specification_id=specification_id,
                operation_id=operation_id,
                candidate_id=candidate["id"],
                payload=execution_payload,
                db=db,
            )
            report = output["run_report"]
        except HTTPException:
            report_record = db.scalar(
                select(ExecutionReportRecord)
                .where(
                    ExecutionReportRecord.project_id == project_id,
                    ExecutionReportRecord.specification_id == specification_id,
                    ExecutionReportRecord.candidate_id == candidate["id"],
                )
                .order_by(ExecutionReportRecord.created_at.desc())
            )
            report = report_record.report if report_record else None
        if report is None:
            results.append(
                {
                    "candidate_id": candidate["id"],
                    "operation_id": operation_id,
                    "outcome": "inconclusive",
                    "assertions": [],
                }
            )
        else:
            expected_positive = (
                benchmark_active
                and operation.get("operation_id") == "getWidget"
                and candidate.get("kind") == "positive-baseline"
                and baseline.path_parameters.get("widget_id") == "13"
            )
            schema_mismatch = any(
                finding.get("kind") == "response_schema_mismatch"
                for finding in report.get("contract_findings", [])
            )
            results.append(
                {
                    "candidate_id": candidate["id"],
                    "operation_id": operation_id,
                    "execution_id": report.get("execution_id"),
                    "outcome": report.get("execution", {}).get("outcome", "inconclusive"),
                    "status_code": report.get("execution", {}).get("status_code"),
                    "elapsed_ms": report.get("execution", {}).get("elapsed_ms"),
                    "assertions": report.get("assertions", []),
                    "contract_findings": report.get("contract_findings", []),
                    "benchmark_positive_case": bool(expected_positive),
                    "seeded_defect_detected": bool(expected_positive and schema_mismatch),
                    "benchmark_schema_mismatch": schema_mismatch,
                }
            )
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    metrics = record.result["metrics"]
    passes = sum(a.get("passed") is True for row in results for a in row.get("assertions", []))
    failures = sum(a.get("passed") is False for row in results for a in row.get("assertions", []))
    inconclusive = sum(row.get("outcome") != "http_response" for row in results)
    metric_updates: dict[str, Any] = {
        "executions_completed": sum(bool(row.get("execution_id")) for row in results),
        "assertion_passes": passes,
        "assertion_failures": failures,
        "inconclusive_outcomes": inconclusive,
        "execution_duration_ms": round(elapsed_ms, 3),
    }
    ground_truth = {
        "available": False,
        "reason": "No seeded-defect benchmark is configured for this run.",
    }
    if benchmark_active and isinstance(benchmark_marker, dict):
        true_positive = sum(bool(row.get("seeded_defect_detected")) for row in results)
        false_negative = 1 - min(true_positive, 1)
        false_positive = sum(
            bool(row.get("benchmark_schema_mismatch")) and not row.get("benchmark_positive_case")
            for row in results
        )
        true_negative = sum(
            not row.get("benchmark_schema_mismatch") and not row.get("benchmark_positive_case")
            for row in results
            if row.get("execution_id")
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else None
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else None
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        )
        metric_updates.update(
            {
                "known_seeded_defects_detected": true_positive,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "detection_rate": float(bool(true_positive)),
                "time_to_first_seeded_defect_ms": next(
                    (
                        round(
                            sum(float(row.get("elapsed_ms") or 0) for row in results[: index + 1]),
                            3,
                        )
                        for index, row in enumerate(results)
                        if row.get("seeded_defect_detected")
                    ),
                    None,
                ),
            }
        )
        ground_truth = {
            "available": True,
            "benchmark_id": benchmark_marker["id"],
            "seeded_defects": benchmark_marker.get("defects", []),
            "confusion_matrix": {
                "true_positive": true_positive,
                "false_positive": false_positive,
                "true_negative": true_negative,
                "false_negative": false_negative,
            },
        }
    safe_baselines = {
        operation_id: {
            "path_parameter_names": sorted(baseline.path_parameters),
            "query_parameter_names": sorted(baseline.query_parameters),
            "header_names": sorted(key.lower() for key in baseline.headers),
            "body_present": baseline.body is not None,
        }
        for operation_id, baseline in payload.baselines.items()
    }
    record.configuration = {
        **record.configuration,
        "execution_base_origin": f"{target_parts.scheme}://{target_parts.netloc}",
        "execution_budget": payload.execution_budget,
        "unsafe_methods_confirmed": payload.confirm_unsafe,
        "redacted_baselines": safe_baselines,
    }
    record.result = {
        **record.result,
        "metrics": {**metrics, **metric_updates},
        "execution_results": results,
        "ground_truth": ground_truth,
    }
    record.status = "executed"
    db.commit()
    db.refresh(record)
    return _record_read(record)


@router.get("/{run_id}/export")
def export_experiment(
    project_id: UUID,
    specification_id: UUID,
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown"] = Query(default="json"),
) -> Response:
    run = _record_read(_get_run(db, project_id, specification_id, run_id))
    if format == "json":
        body = json.dumps(run, ensure_ascii=False, indent=2)
        media_type, suffix = "application/json", "json"
    else:
        metrics = run["result"]["metrics"]
        body = "\n".join(
            [
                f"# IntelAPI experiment {run['id']}",
                "",
                f"- Approach: {run['approach']}",
                f"- Status: {run['status']}",
                "",
                "## Metrics",
                *[f"- {key}: {value}" for key, value in metrics.items()],
                "",
                "Ground-truth defect metrics unavailable unless a seeded benchmark is configured.",
            ]
        )
        media_type, suffix = "text/markdown; charset=utf-8", "md"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="intelapi-experiment-{run_id}.{suffix}"'
        },
    )


@router.get("/comparison/export")
def export_comparison(
    project_id: UUID,
    specification_id: UUID,
    baseline_run_id: UUID,
    semantic_run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["json", "markdown"] = Query(default="json"),
) -> Response:
    comparison = compare_experiments(
        project_id, specification_id, baseline_run_id, semantic_run_id, db
    )
    if format == "json":
        body = json.dumps(comparison, ensure_ascii=False, indent=2)
        media_type, suffix = "application/json", "json"
    else:
        baseline = comparison["baseline"]
        semantic = comparison["semantic_guided"]
        keys = sorted(set(baseline["result"]["metrics"]) | set(semantic["result"]["metrics"]))
        lines = [
            "# IntelAPI experiment comparison",
            "",
            f"- Specification: `{specification_id}`",
            f"- Same configured candidate budget: {comparison['same_candidate_budget']}",
            "",
            "| Metric | Contract baseline | Semantic guided |",
            "|---|---:|---:|",
        ]
        lines.extend(
            f"| {key} | {baseline['result']['metrics'].get(key)} | "
            f"{semantic['result']['metrics'].get(key)} |"
            for key in keys
        )
        lines.extend(
            [
                "",
                "Defect metrics unavailable without a ground-truth benchmark.",
            ]
        )
        body = "\n".join(lines)
        media_type, suffix = "text/markdown; charset=utf-8", "md"
    filename = f"intelapi-comparison-{baseline_run_id}-{semantic_run_id}.{suffix}"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
