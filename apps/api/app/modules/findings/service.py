"""Evidence-first finding creation from explicit failed assertions."""

from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.execution import Execution
from app.models.finding import EvidenceReference, Finding
from app.models.health_check import AssertionResult, HealthCheck

SENSITIVE_TARGET_PARTS = ("password", "secret", "token", "authorization", "cookie", "credential")


def is_sensitive_target(target: str | None) -> bool:
    lowered = (target or "").lower()
    return any(part in lowered for part in SENSITIVE_TARGET_PARTS)


def record_assertion_findings(
    db: Session,
    health_check: HealthCheck,
    execution: Execution,
    results: list[AssertionResult],
) -> list[Finding]:
    """Create deduplicated potential findings with declared and observed sources."""
    findings: list[Finding] = []
    for result in results:
        if (
            execution.status != "completed"
            or result.passed
            or result.actual is None
            or result.expected == result.actual
        ):
            continue
        identity = f"health:{health_check.id}:execution:{execution.id}:assertion:{result.id}"
        finding_key = sha256(identity.encode("utf-8")).hexdigest()
        finding = Finding(
            project_id=health_check.project_id,
            execution_id=execution.id,
            finding_key=finding_key,
            title="Configured health assertion mismatch",
            summary=(
                f"The configured {result.assertion_type} assertion failed. "
                "This is a potential finding that requires human review, not a confirmed defect."
            ),
            classification="assertion_mismatch",
            machine_severity="medium",
            confidence=0.8,
            user_status="open",
        )
        db.add(finding)
        db.flush()
        details = {
            "assertion_type": result.assertion_type,
            "expected": result.expected,
            "actual": result.actual,
        }
        db.add_all(
            [
                EvidenceReference(
                    project_id=health_check.project_id,
                    finding_id=finding.id,
                    assertion_result_id=result.id,
                    execution_id=execution.id,
                    provenance="DECLARED",
                    evidence_type="failed_health_assertion",
                    excerpt=(
                        f"Expected value {result.expected!r}; observed value {result.actual!r}."
                    )[:2000],
                    evidence_metadata=details,
                ),
                EvidenceReference(
                    project_id=health_check.project_id,
                    finding_id=finding.id,
                    execution_id=execution.id,
                    provenance="OBSERVED",
                    evidence_type="execution_response",
                    excerpt=(
                        f"HTTP {execution.response_status_code}; "
                        f"execution status {execution.status}."
                    ),
                    evidence_metadata={"response_status_code": execution.response_status_code},
                ),
            ]
        )
        findings.append(finding)
    return findings
