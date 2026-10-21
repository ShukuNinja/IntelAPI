from app.models.execution import Execution
from app.models.execution_evidence import ExecutionEvidence


def build_execution_evidence(execution: Execution) -> list[ExecutionEvidence]:
    """Create deterministic evidence records from a completed or failed execution."""
    if execution.status == "failed":
        return [
            ExecutionEvidence(
                kind="execution_error",
                severity="error",
                title="Request execution failed",
                message=execution.error_message or "The request could not be completed.",
                details={"error_code": execution.error_code or "EXECUTION_FAILED"},
            )
        ]
    evidence: list[ExecutionEvidence] = []
    if execution.response_status_code is not None:
        code = execution.response_status_code
        evidence.append(
            ExecutionEvidence(
                kind="http_status",
                severity="info" if 200 <= code < 400 else "warning",
                title=f"HTTP response status {code}",
                message=f"The endpoint returned HTTP {code}.",
                details={"status_code": code},
            )
        )
    if execution.duration_ms is not None:
        evidence.append(
            ExecutionEvidence(
                kind="latency",
                severity="info",
                title="Request latency recorded",
                message=f"Request completed in {execution.duration_ms} ms.",
                details={"duration_ms": execution.duration_ms},
            )
        )
    return evidence
