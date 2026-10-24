"""Small, deterministic OpenAPI JSON normalizer used by import and preview routes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import yaml

SUPPORTED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
MAX_SPECIFICATION_BYTES = 2_000_000
MAX_REPORT_OPERATIONS = 100
MAX_REPORT_CANDIDATES = 500


class SpecificationError(ValueError):
    """The supplied document is not a supported OpenAPI document."""


def parse_specification_content(content: str, source_format: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_SPECIFICATION_BYTES:
        raise SpecificationError("The specification exceeds the 2 MB import limit.")
    if source_format not in {"json", "yaml"}:
        raise SpecificationError("Specify either json or yaml as the source format.")
    try:
        document = json.loads(content) if source_format == "json" else yaml.safe_load(content)
    except json.JSONDecodeError as exc:
        raise SpecificationError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}.") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise SpecificationError(f"Invalid YAML{location}.") from exc
    # PyYAML resolves some plain scalars (for example dates) to Python objects
    # that cannot be returned by JSON APIs or stored in JSON database columns.
    document = json.loads(json.dumps(document, default=str))
    return parse_specification(document)


def parse_specification(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise SpecificationError("The specification root must be a JSON object.")
    if document.get("swagger") == "2.0":
        document = normalize_swagger_2(document)
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
                    "parameters": _resolve_local_refs(
                        _merge_parameters(
                            path_item.get("parameters", []), operation.get("parameters", [])
                        ),
                        document,
                    ),
                    "request_body": _resolve_local_refs(operation.get("requestBody", {}), document),
                    "responses": _resolve_local_refs(operation.get("responses", {}), document),
                }
            )
    return {
        "specification": {
            "title": document["info"].get("title", "Untitled API"),
            "version": version,
        },
        "servers": document.get("servers", []) if isinstance(document.get("servers"), list) else [],
        "operations": operations,
    }


def _resolve_local_refs(
    value: Any,
    document: dict[str, Any],
    depth: int = 0,
    seen: frozenset[str] = frozenset(),
) -> Any:
    """Inline bounded local JSON pointers; never performs network access for refs."""
    if depth > 20:
        return value
    if isinstance(value, list):
        return [_resolve_local_refs(item, document, depth + 1, seen) for item in value]
    if not isinstance(value, dict):
        return value
    reference = value.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/") and reference not in seen:
        target: Any = document
        try:
            for segment in reference[2:].split("/"):
                token = segment.replace("~1", "/").replace("~0", "~")
                target = target[token]
        except (KeyError, TypeError):
            target = None
        if isinstance(target, dict):
            merged = {**target, **{key: item for key, item in value.items() if key != "$ref"}}
            return _resolve_local_refs(merged, document, depth + 1, seen | {reference})
    return {
        key: _resolve_local_refs(item, document, depth + 1, seen) for key, item in value.items()
    }


def normalize_swagger_2(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize the supported Swagger 2.0 subset to an OpenAPI 3.0 document."""
    info = document.get("info")
    paths = document.get("paths")
    if not isinstance(info, dict) or not isinstance(paths, dict):
        raise SpecificationError("Swagger 2.0 requires info and paths objects.")
    security_definitions = document.get("securityDefinitions", {})
    if not isinstance(security_definitions, dict):
        raise SpecificationError("Swagger 2.0 securityDefinitions must be an object.")

    normalized_paths: dict[str, Any] = {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        new_item: dict[str, Any] = {}
        for key, value in path_item.items():
            if key == "parameters" and isinstance(value, list):
                new_item[key] = [_normalize_swagger_parameter(parameter) for parameter in value]
            elif (
                isinstance(key, str)
                and key.lower() in SUPPORTED_METHODS
                and isinstance(value, dict)
            ):
                operation = deepcopy(value)
                parameters = operation.pop("parameters", [])
                regular_parameters = []
                body_parameters = []
                form_parameters = []
                for parameter in parameters if isinstance(parameters, list) else []:
                    if not isinstance(parameter, dict):
                        continue
                    if parameter.get("in") == "body":
                        body_parameters.append(parameter)
                    elif parameter.get("in") == "formData":
                        form_parameters.append(parameter)
                    else:
                        regular_parameters.append(_normalize_swagger_parameter(parameter))
                if regular_parameters:
                    operation["parameters"] = regular_parameters
                if len(body_parameters) > 1 or (body_parameters and form_parameters):
                    raise SpecificationError(
                        "A Swagger operation cannot combine multiple body parameters or body and "
                        "formData parameters."
                    )
                if body_parameters:
                    media_types = _swagger_media_types(operation, document, "application/json")
                    body_parameter = body_parameters[0]
                    schema = body_parameter.get("schema", {})
                    operation["requestBody"] = {
                        "required": body_parameter.get("required", False),
                        "description": body_parameter.get("description", ""),
                        "content": {media_type: {"schema": schema} for media_type in media_types},
                    }
                elif form_parameters:
                    properties = {}
                    required = []
                    for parameter in form_parameters:
                        if not isinstance(parameter.get("name"), str):
                            continue
                        normalized = _normalize_swagger_parameter(parameter)
                        properties[parameter["name"]] = normalized["schema"]
                        if parameter.get("required"):
                            required.append(parameter["name"])
                    has_file = any(prop.get("format") == "binary" for prop in properties.values())
                    default_media = (
                        "multipart/form-data" if has_file else "application/x-www-form-urlencoded"
                    )
                    media_types = _swagger_media_types(operation, document, default_media)
                    operation["requestBody"] = {
                        "required": bool(required),
                        "content": {
                            media_type: {
                                "schema": {
                                    "type": "object",
                                    "properties": properties,
                                    "required": required,
                                }
                            }
                            for media_type in media_types
                        },
                    }
                operation.pop("consumes", None)
                operation.pop("produces", None)
                new_item[key] = operation
            else:
                new_item[key] = value
        normalized_paths[path] = new_item

    servers = []
    host = document.get("host")
    if isinstance(host, str) and host:
        schemes = document.get("schemes") or ["https"]
        base_path = document.get("basePath", "")
        if isinstance(schemes, list) and all(isinstance(scheme, str) for scheme in schemes):
            if not isinstance(base_path, str):
                base_path = ""
            servers = [{"url": f"{scheme}://{host}{base_path}"} for scheme in schemes]
    return {
        "openapi": "3.0.0",
        "info": info,
        "servers": servers,
        "paths": normalized_paths,
        "components": {
            "schemas": document.get("definitions", {}),
            "parameters": document.get("parameters", {}),
            "responses": document.get("responses", {}),
            "securitySchemes": {
                name: _normalize_security_scheme(scheme)
                for name, scheme in security_definitions.items()
            },
        },
    }


def _normalize_swagger_parameter(parameter: Any) -> Any:
    if not isinstance(parameter, dict) or "schema" in parameter:
        return parameter
    schema_keys = {
        "type",
        "format",
        "items",
        "enum",
        "default",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "uniqueItems",
        "minItems",
        "maxItems",
    }
    normalized = {key: value for key, value in parameter.items() if key not in schema_keys}
    normalized["schema"] = {key: value for key, value in parameter.items() if key in schema_keys}
    if normalized["schema"].get("type") == "file":
        normalized["schema"] = {"type": "string", "format": "binary"}
    return normalized


def _swagger_media_types(
    operation: dict[str, Any], document: dict[str, Any], default: str
) -> list[str]:
    media_types = operation.get("consumes") or document.get("consumes")
    if not isinstance(media_types, list) or not all(
        isinstance(media_type, str) for media_type in media_types
    ):
        return [default]
    return media_types or [default]


def _normalize_security_scheme(scheme: Any) -> Any:
    if not isinstance(scheme, dict):
        return scheme
    normalized = deepcopy(scheme)
    if normalized.get("type") == "basic":
        normalized["type"] = "http"
        normalized["scheme"] = "basic"
    if normalized.get("type") == "oauth2":
        flow = normalized.pop("flow", None)
        flow_names = {
            "implicit": "implicit",
            "password": "password",
            "application": "clientCredentials",
            "accessCode": "authorizationCode",
        }
        if flow in flow_names:
            normalized["flows"] = {
                flow_names[flow]: {
                    "authorizationUrl": normalized.pop("authorizationUrl", ""),
                    "tokenUrl": normalized.pop("tokenUrl", ""),
                    "scopes": normalized.pop("scopes", {}),
                }
            }
    return normalized


def generate_candidates(operation: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    """Return explainable boundary candidates without network calls or randomness."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    candidates: list[dict[str, Any]] = []
    scope = operation.get("id") or f"{operation.get('method', '')}:{operation.get('path', '')}"
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
                    scope,
                )
            )
        if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
            candidates.append(
                _candidate(
                    "parameter-enum-boundary",
                    f"Probe a value outside the declared enum for '{name}'.",
                    {
                        "set_parameter": {
                            "in": parameter.get("in", "query"),
                            "name": name,
                            "value": _enum_sentinel(schema["enum"]),
                        }
                    },
                    scope,
                )
            )
        elif schema.get("type") == "integer" and isinstance(schema.get("minimum"), (int, float)):
            candidates.append(
                _candidate(
                    "parameter-minimum-boundary",
                    f"Probe one below the declared minimum for '{name}'.",
                    {name: schema["minimum"] - 1},
                    scope,
                )
            )
        elif (
            schema.get("type") == "string"
            and isinstance(schema.get("maxLength"), int)
            and 0 <= schema["maxLength"] < 4096
        ):
            candidates.append(
                _candidate(
                    "parameter-length-boundary",
                    f"Probe a string one character longer than maxLength for '{name}'.",
                    {name: "x" * (schema["maxLength"] + 1)},
                    scope,
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
                        scope,
                    )
                )
    if isinstance(properties, dict):
        for name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                continue
            if isinstance(property_schema.get("enum"), list) and property_schema["enum"]:
                candidates.append(
                    _candidate(
                        "body-enum-boundary",
                        f"Probe a value outside the declared enum for body property '{name}'.",
                        {name: _enum_sentinel(property_schema["enum"])},
                        scope,
                    )
                )
            elif property_schema.get("type") == "integer" and isinstance(
                property_schema.get("minimum"), (int, float)
            ):
                candidates.append(
                    _candidate(
                        "body-minimum-boundary",
                        f"Probe one below the declared minimum for body property '{name}'.",
                        {name: property_schema["minimum"] - 1},
                        scope,
                    )
                )
            elif property_schema.get("type") == "string" and isinstance(
                property_schema.get("maxLength"), int
            ):
                candidates.append(
                    _candidate(
                        "body-length-boundary",
                        f"Probe one character above maxLength for body property '{name}'.",
                        {name: "x" * min(property_schema["maxLength"] + 1, 4097)},
                        scope,
                    )
                )
    candidates.append(
        _candidate(
            "positive-baseline",
            "Execute the user-supplied valid baseline request without a contract mutation.",
            {},
            scope,
        )
    )
    return candidates[:limit]


def generate_generation_report(
    operations: list[dict[str, Any]], per_operation_limit: int = 20
) -> dict[str, Any]:
    """Build a bounded, endpoint-wise preview report from actual normalized operations."""
    if not operations or len(operations) > MAX_REPORT_OPERATIONS:
        raise ValueError(f"Provide between 1 and {MAX_REPORT_OPERATIONS} operations.")
    if per_operation_limit < 1 or per_operation_limit > 20:
        raise ValueError("per_operation_limit must be between 1 and 20.")

    endpoints = []
    total = 0
    truncated = False
    for index, operation in enumerate(operations):
        all_candidates = generate_candidates(operation, 100)
        if len(all_candidates) > per_operation_limit:
            truncated = True
        candidates = all_candidates[:per_operation_limit]
        remaining = MAX_REPORT_CANDIDATES - total
        if len(candidates) > remaining:
            candidates = candidates[:remaining]
            truncated = True
        total += len(candidates)
        endpoints.append(
            {
                "operation": {
                    "id": operation.get("id"),
                    "operation_id": operation.get("operation_id"),
                    "method": operation.get("method"),
                    "path": operation.get("path"),
                    "summary": operation.get("summary", ""),
                },
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )
        if total == MAX_REPORT_CANDIDATES:
            truncated = truncated or index < len(operations) - 1
            break
    return {
        "policy_version": "schema-preview-v1",
        "summary": {
            "operation_count": len(endpoints),
            "candidate_count": total,
            "endpoints_with_candidates": sum(
                endpoint["candidate_count"] > 0 for endpoint in endpoints
            ),
            "truncated": truncated,
        },
        "endpoints": endpoints,
    }


def _merge_parameters(path_parameters: Any, operation_parameters: Any) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in (path_parameters, operation_parameters):
        if isinstance(item, list):
            for parameter in item:
                if isinstance(parameter, dict) and isinstance(parameter.get("name"), str):
                    merged[(parameter.get("in", "query"), parameter["name"])] = parameter
    return list(merged.values())


def _enum_sentinel(values: list[Any]) -> str:
    candidate = "__intelapi_outside_enum__"
    while candidate in values:
        candidate += "_x"
    return candidate


def _candidate(kind: str, reason: str, mutation: dict[str, Any], scope: str = "") -> dict[str, Any]:
    seed = json.dumps([scope, kind, reason, mutation], sort_keys=True, separators=(",", ":"))
    return {
        "id": hashlib.sha256(seed.encode()).hexdigest()[:20],
        "kind": kind,
        "reason": reason,
        "mutation": mutation,
        "validation_status": "preview",
    }
