"""Tests for deterministic observation classification."""

from app.modules.analysis.classifier import classify_observation
from app.modules.analysis.models import (
    AnalysisObservation,
    ClassificationDisposition,
    FindingCategory,
    ObservationKind,
)
from app.modules.api_understanding.models import SourceReference
from app.modules.knowledge.models import FactProvenance


def make_observation(
    kind: ObservationKind,
    *,
    expected=None,
    actual=None,
    has_expected=False,
    has_actual=False,
    status_code=None,
) -> AnalysisObservation:
    return AnalysisObservation(
        observation_id="obs-001",
        operation_key="GET /items/{item_id}",
        kind=kind,
        summary="Test observation",
        source_ref=SourceReference(pointer="#/paths/~1items~1{item_id}/get"),
        provenance=FactProvenance.OBSERVED,
        expected=expected,
        actual=actual,
        has_expected=has_expected,
        has_actual=has_actual,
        status_code=status_code,
        assertion_id="assert-001",
    )


def test_assertion_mismatch_produces_potential_finding():
    observation = make_observation(
        ObservationKind.ASSERTION_MISMATCH,
        expected=200,
        actual=500,
        has_expected=True,
        has_actual=True,
    )

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.POTENTIAL_FINDING
    assert result.finding is not None
    assert result.finding.category == FindingCategory.CONTRACT_MISMATCH
    assert result.finding.confidence == 0.8
    assert result.finding.observation_id == observation.observation_id
    assert "not a confirmed defect" in result.rationale


def test_schema_mismatch_preserves_provenance_and_source():
    source_ref = SourceReference(pointer="#/components/schemas/Item")
    observation = AnalysisObservation(
        observation_id="obs-schema",
        operation_key="GET /items",
        kind=ObservationKind.SCHEMA_MISMATCH,
        summary="Property type mismatch",
        source_ref=source_ref,
        provenance=FactProvenance.DECLARED,
        expected="string",
        actual="integer",
        has_expected=True,
        has_actual=True,
    )

    result = classify_observation(observation)

    assert result.finding is not None
    assert result.finding.source_ref == source_ref
    assert result.finding.provenance == FactProvenance.DECLARED
    assert result.finding.assertion_id is None


def test_http_non_2xx_alone_is_only_an_observation():
    observation = make_observation(
        ObservationKind.HTTP_RESPONSE,
        status_code=500,
    )

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.OBSERVATION
    assert result.finding is None


def test_transport_failure_alone_is_not_a_contract_finding():
    observation = make_observation(ObservationKind.TRANSPORT_FAILURE)

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.OBSERVATION
    assert result.finding is None


def test_missing_expected_or_actual_value_is_insufficient_evidence():
    observation = make_observation(
        ObservationKind.ASSERTION_MISMATCH,
        expected=200,
        has_expected=True,
        has_actual=False,
    )

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.OBSERVATION
    assert result.finding is None
    assert "insufficient" in result.rationale


def test_matching_values_do_not_produce_a_finding():
    observation = make_observation(
        ObservationKind.ASSERTION_MISMATCH,
        expected=200,
        actual=200,
        has_expected=True,
        has_actual=True,
    )

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.OBSERVATION
    assert result.finding is None


def test_json_null_can_be_classified_as_an_actual_value():
    observation = make_observation(
        ObservationKind.SCHEMA_MISMATCH,
        expected="string",
        actual=None,
        has_expected=True,
        has_actual=True,
    )

    result = classify_observation(observation)

    assert result.disposition == ClassificationDisposition.POTENTIAL_FINDING
    assert result.finding is not None


def test_classification_is_deterministic():
    observation = make_observation(
        ObservationKind.ASSERTION_MISMATCH,
        expected=200,
        actual=500,
        has_expected=True,
        has_actual=True,
    )

    first = classify_observation(observation)
    second = classify_observation(observation)

    assert first == second
    assert first.finding is not None
    assert second.finding is not None
    assert first.finding.candidate_id == second.finding.candidate_id
