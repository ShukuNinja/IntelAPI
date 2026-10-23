"""Deterministic completeness checks for an imported OpenAPI document."""

from typing import Any


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _parameter_pointer(
    document: dict[str, Any], path: str, method: str, parameter: dict[str, Any]
) -> str:
    path_item = document.get("paths", {}).get(path, {})
    operation = path_item.get(method, {}) if isinstance(path_item, dict) else {}
    name, location = parameter.get("name"), parameter.get("in")
    for pointer, items in (
        (f"/paths/{_pointer_part(path)}/{method}/parameters", operation.get("parameters", [])),
        (f"/paths/{_pointer_part(path)}/parameters", path_item.get("parameters", [])),
    ):
        if isinstance(items, list):
            for index, item in enumerate(items):
                if (
                    isinstance(item, dict)
                    and item.get("name") == name
                    and item.get("in") == location
                ):
                    return f"{pointer}/{index}"
    return f"/paths/{_pointer_part(path)}/{method}/parameters"


def _request_body_pointer(document: dict[str, Any], path: str, method: str) -> str:
    base = f"/paths/{_pointer_part(path)}/{method}"
    if document.get("swagger") == "2.0":
        parameters = document.get("paths", {}).get(path, {}).get(method, {}).get("parameters", [])
        if isinstance(parameters, list):
            for index, parameter in enumerate(parameters):
                if isinstance(parameter, dict) and parameter.get("in") in {"body", "formData"}:
                    return f"{base}/parameters/{index}"
    return f"{base}/requestBody"


def analyze_readiness(document: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    operation_results = []

    def add(
        code: str,
        severity: str,
        message: str,
        pointer: str,
        operation_id: str | None = None,
    ) -> None:
        finding = {
            "code": code,
            "severity": severity,
            "message": message,
            "evidence": {"json_pointer": pointer},
        }
        if operation_id:
            finding["operation_id"] = operation_id
        findings.append(finding)

    for operation in operations:
        method = str(operation.get("method", "")).lower()
        path = str(operation.get("path", ""))
        pointer = f"/paths/{_pointer_part(path)}/{method}"
        operation_findings_before = len(findings)
        operation_id = operation.get("id")
        if not operation.get("summary"):
            add(
                "missing_summary",
                "low",
                "Operation has no summary for API discovery.",
                pointer,
                operation_id,
            )
        if not operation.get("operation_id"):
            add(
                "missing_operation_id",
                "low",
                "Operation has no stable declared operationId.",
                pointer,
                operation_id,
            )
        responses = operation.get("responses")
        if not isinstance(responses, dict) or not responses:
            add(
                "missing_responses",
                "high",
                "Operation does not document any responses.",
                f"{pointer}/responses",
                operation_id,
            )
        parameters = operation.get("parameters", [])
        if isinstance(parameters, list):
            for index, parameter in enumerate(parameters):
                if isinstance(parameter, dict) and not isinstance(parameter.get("schema"), dict):
                    add(
                        "parameter_schema_missing",
                        "medium",
                        f"Parameter '{parameter.get('name', 'unnamed')}' has no inline schema.",
                        f"{pointer}/parameters/{index}",
                        operation_id,
                    )
        request_body = operation.get("request_body")
        if isinstance(request_body, dict) and request_body:
            body_pointer = _request_body_pointer(document, path, method)
            content = request_body.get("content")
            if not isinstance(content, dict) or not content:
                add(
                    "request_body_media_missing",
                    "medium",
                    "Request body has no declared media type.",
                    f"{body_pointer}/content",
                    operation_id,
                )
            elif not any(
                isinstance(media, dict) and isinstance(media.get("schema"), dict)
                for media in content.values()
            ):
                add(
                    "request_body_schema_missing",
                    "medium",
                    "Request body media types have no schema.",
                    f"{body_pointer}/content",
                    operation_id,
                )
        operation_findings = findings[operation_findings_before:]
        operation_results.append(
            {
                "operation_id": operation_id,
                "method": operation.get("method"),
                "path": path,
                "finding_count": len(operation_findings),
                "readiness": (
                    "needs_attention"
                    if any(item["severity"] in {"high", "medium"} for item in operation_findings)
                    else "review"
                    if operation_findings
                    else "ready"
                ),
            }
        )

    if not operations:
        add(
            "no_operations", "high", "Specification contains no supported API operations.", "/paths"
        )

    servers = document.get("servers")
    if not isinstance(servers, list) or not any(
        isinstance(server, dict) and isinstance(server.get("url"), str) and server["url"]
        for server in servers
    ):
        add(
            "server_url_missing",
            "low",
            "No server URL is declared; execution needs a supplied base URL.",
            "/servers",
        )

    summary = {
        "operation_count": len(operations),
        "finding_count": len(findings),
        "high_count": sum(item["severity"] == "high" for item in findings),
        "medium_count": sum(item["severity"] == "medium" for item in findings),
        "low_count": sum(item["severity"] == "low" for item in findings),
        "operations_needing_attention": sum(
            item["readiness"] == "needs_attention" for item in operation_results
        ),
    }
    return {
        "analysis_version": "readiness-rules-v1",
        "scope": "documented_completeness_only",
        "summary": summary,
        "operations": operation_results,
        "findings": findings,
        "limitations": [
            "Readiness findings measure documented completeness, not runtime correctness "
            "or security.",
            "A missing field may be intentional; review each finding before changing the contract.",
            "Remote and cyclic references are not resolved by this analyzer.",
        ],
    }
