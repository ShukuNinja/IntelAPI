from types import SimpleNamespace

from app.modules.evidence.service import build_execution_evidence


def test_evidence_for_http_error_response_is_warning() -> None:
    execution = SimpleNamespace(
        status="completed",
        response_status_code=500,
        duration_ms=25,
        error_message=None,
        error_code=None,
    )
    evidence = build_execution_evidence(execution)  # type: ignore[arg-type]
    assert evidence[0].kind == "http_status"
    assert evidence[0].severity == "warning"
    assert evidence[1].kind == "latency"


def test_evidence_for_execution_failure_is_error() -> None:
    execution = SimpleNamespace(
        status="failed",
        response_status_code=None,
        duration_ms=50,
        error_message="The outbound request timed out.",
        error_code="TIMEOUT",
    )
    evidence = build_execution_evidence(execution)  # type: ignore[arg-type]
    assert len(evidence) == 1
    assert evidence[0].severity == "error"
