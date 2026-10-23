"""Small, deterministic OpenAPI JSON normalizer used by import and preview routes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SUPPORTED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


class SpecificationError(ValueError):
    """The supplied document is not a supported OpenAPI document."""


def parse_specification(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise SpecificationError("The specification root must be a JSON object.")
    version = document.get("openapi")
    if not isinstance(version, str) or not (
        version.startswith("3.0.") or version.startswith("3.1.")
    ):
        raise SpecificationError("Only OpenAPI 3.0.x and 3.1.x documents are supported.")
    if not isinstance(document.get("info"), dict):
        raise SpecificationError("The specification must include an info object.")
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise SpecificationError("The specification must include a paths object.")

    operations = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in SUPPORTED_METHODS or not isinstance(operation, dict):
                continue
            identity = operation.get("operationId") or f"{method.lower()} {path}"
            stable_id = hashlib.sha256(f"{method.lower()}:{path}:{identity}".encode()).hexdigest()[
                :20
            ]
            operations.append(
                {
                    "id": stable_id,
                    "operation_id": operation.get("operationId"),
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": operation.get("tags", []),
                    "parameters": _merge_parameters(
                        path_item.get("parameters", []), operation.get("parameters", [])
                    ),
                    "request_body": operation.get("requestBody", {}),
                }
            )
    return {
        "specification": {
            "title": document["info"].get("title", "Untitled API"),
            "version": version,
        },
        "operations": operations,
    }


def generate_candidates(operation: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    """Return explainable boundary candidates without network calls or randomness."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    candidates: list[dict[str, Any]] = []
    for parameter in operation.get("parameters", []):
        if not isinstance(parameter, dict) or not isinstance(parameter.get("schema"), dict):
            continue
        name = parameter.get("name", "parameter")
        schema = parameter["schema"]
        if parameter.get("required"):
            candidates.append(
                _candidate(
                    "required-parameter-omitted",
                    f"Omit required {parameter.get('in', 'query')} parameter '{name}'.",
                    {"remove_parameter": {"in": parameter.get("in", "query"), "name": name}},
                )
            )
        if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
            candidates.append(
                _candidate(
                    "parameter-enum-boundary",
                    f"Probe a value outside the declared enum for '{name}'.",
                    {name: "__outside_enum__"},
                )
            )
        elif schema.get("type") == "integer" and isinstance(schema.get("minimum"), (int, float)):
            candidates.append(
                _candidate(
                    "parameter-minimum-boundary",
                    f"Probe one below the declared minimum for '{name}'.",
                    {name: schema["minimum"] - 1},
                )
            )
        elif schema.get("type") == "string" and isinstance(schema.get("maxLength"), int):
            candidates.append(
                _candidate(
                    "parameter-length-boundary",
                    f"Probe a string one character longer than maxLength for '{name}'.",
                    {name: "x" * min(schema["maxLength"] + 1, 256)},
                )
            )
    body = operation.get("request_body", {})
    content = body.get("content", {}) if isinstance(body, dict) else {}
    media = content.get("application/json", {}) if isinstance(content, dict) else {}
    schema = media.get("schema", {}) if isinstance(media, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if isinstance(required, list):
        for name in required:
            if name in properties:
                candidates.append(
                    _candidate(
                        "required-body-property-omitted",
                        f"Omit required request-body property '{name}'.",
                        {"remove_property": name},
                    )
                )
    return candidates[:limit]


def _merge_parameters(path_parameters: Any, operation_parameters: Any) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in (path_parameters, operation_parameters):
        if isinstance(item, list):
            for parameter in item:
                if isinstance(parameter, dict) and isinstance(parameter.get("name"), str):
                    merged[(parameter.get("in", "query"), parameter["name"])] = parameter
    return list(merged.values())


def _candidate(kind: str, reason: str, mutation: dict[str, Any]) -> dict[str, Any]:
    seed = json.dumps([kind, reason, mutation], sort_keys=True, separators=(",", ":"))
    return {
        "id": hashlib.sha256(seed.encode()).hexdigest()[:20],
        "kind": kind,
        "reason": reason,
        "mutation": mutation,
        "validation_status": "preview",
    }
