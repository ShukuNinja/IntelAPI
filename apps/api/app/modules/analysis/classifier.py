"""Deterministic classification of API observations."""

import hashlib
import json

from app.modules.analysis.models import (
    AnalysisObservation,
    ClassificationDisposition,
    ClassificationResult,
    FindingCandidate,
    FindingCategory,
    ObservationKind,
)


def _candidate_id(observation: AnalysisObservation) -> str:
    """Return a stable identifier for the same observation and classification."""
    identity = {
        "observation_id": observation.observation_id,
        "operation_key": observation.operation_key,
        "kind": observation.kind.value,
        "expected": observation.expected,
        "actual": observation.actual,
        "assertion_id": observation.assertion_id,
        "source_pointer": observation.source_ref.pointer,
    }
    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def classify_observation(
    observation: AnalysisObservation,
) -> ClassificationResult:
    """Classify explicit mismatches without asserting that a defect is confirmed."""
    if observation.kind not in {
        ObservationKind.ASSERTION_MISMATCH,
        ObservationKind.SCHEMA_MISMATCH,
    }:
        return ClassificationResult(
            observation_id=observation.observation_id,
            disposition=ClassificationDisposition.OBSERVATION,
            rationale=(
                "The available evidence records an observation but does not "
                "establish a contract mismatch."
            ),
        )

    if not observation.has_expected or not observation.has_actual:
        return ClassificationResult(
            observation_id=observation.observation_id,
            disposition=ClassificationDisposition.OBSERVATION,
            rationale=(
                "Expected and actual values are required to classify an "
                "explicit mismatch; the evidence is insufficient."
            ),
        )

    if observation.expected == observation.actual:
        return ClassificationResult(
            observation_id=observation.observation_id,
            disposition=ClassificationDisposition.OBSERVATION,
            rationale=(
                "Expected and actual values match; no mismatch is supported."
            ),
        )

    mismatch_kind = (
        "schema"
        if observation.kind == ObservationKind.SCHEMA_MISMATCH
        else "assertion"
    )
    rationale = (
        f"An explicit {mismatch_kind} mismatch was recorded: "
        f"expected {observation.expected!r}, observed {observation.actual!r}. "
        "This is a potential finding, not a confirmed defect."
    )

    finding = FindingCandidate(
        candidate_id=_candidate_id(observation),
        operation_key=observation.operation_key,
        category=FindingCategory.CONTRACT_MISMATCH,
        title=f"API {mismatch_kind} mismatch",
        confidence=0.8,
        rationale=rationale,
        observation_id=observation.observation_id,
        assertion_id=observation.assertion_id,
        source_ref=observation.source_ref,
        provenance=observation.provenance,
    )

    return ClassificationResult(
        observation_id=observation.observation_id,
        disposition=ClassificationDisposition.POTENTIAL_FINDING,
        rationale=rationale,
        finding=finding,
    )

