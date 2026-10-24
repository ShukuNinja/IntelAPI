"""Deterministic, provenance-preserving semantic feature extraction and ranking."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z][a-z0-9]*|[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[0-9]+")
INTENT_WORDS = {
    "create": {"create", "add", "register", "submit", "post"},
    "read": {"get", "read", "list", "fetch", "search", "retrieve"},
    "update": {"update", "edit", "patch", "replace", "modify"},
    "delete": {"delete", "remove", "cancel", "revoke"},
}
IDENTIFIER_NAMES = {"id", "uuid", "key", "identifier", "user_id", "account_id", "order_id"}
CONSTRAINT_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "enum",
    "minItems",
    "maxItems",
    "format",
)


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [token.lower() for token in TOKEN_RE.findall(value.replace("_", " ").replace("-", " "))]


def extract_semantic_facts(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    def add(
        kind: str,
        value: Any,
        operation: dict[str, Any],
        source: str,
        rule: str,
        evidence: str = "inferred",
        strength: float = 0.7,
    ) -> None:
        facts.append(
            {
                "fact_type": kind,
                "value": value,
                "source_operation": operation.get("id"),
                "source_schema": source if "schema" in source else None,
                "source_location": source,
                "rule": rule,
                "evidence_strength": strength,
                "evidence": evidence,
            }
        )

    for op in operations:
        method = str(op.get("method", "")).lower()
        path = str(op.get("path", ""))
        operation_id = str(op.get("operation_id") or "")
        descriptions = " ".join(str(op.get(key, "")) for key in ("summary", "description"))
        words = set(_tokens(" ".join([operation_id, descriptions, *path.split("/")])))
        intents = [intent for intent, terms in INTENT_WORDS.items() if words & terms]
        if method in {"post"}:
            inferred = "create"
        elif method in {"get", "head"}:
            inferred = "read"
        elif method in {"put", "patch"}:
            inferred = "update"
        elif method == "delete":
            inferred = "delete"
        else:
            inferred = "action"
        intent = next((item for item in intents if item == inferred), inferred)
        add(
            "operation_intent",
            intent,
            op,
            "operation.method/operationId/summary/description",
            "method_mapping_with_text_evidence",
            "direct" if method in {"get", "post", "put", "patch", "delete"} else "inferred",
            0.95 if method in {"get", "post", "put", "patch", "delete"} else 0.55,
        )
        resource = next((part for part in path.split("/") if part and not part.startswith("{")), "")
        if resource:
            add(
                "resource_entity",
                resource.rstrip("s"),
                op,
                "path",
                "first_static_path_segment_singularized",
                strength=0.65,
            )
        path_params = re.findall(r"\{([^}]+)\}", path)
        for name in path_params:
            add(
                "resource_identifier",
                {"name": name, "resource": resource},
                op,
                f"path.parameter.{name}",
                "path_parameter_is_resource_identifier",
                "direct",
                0.9,
            )
        for pindex, parameter in enumerate(op.get("parameters", [])):
            if not isinstance(parameter, dict):
                continue
            name = str(parameter.get("name", ""))
            raw_schema = parameter.get("schema")
            schema: dict[str, Any] = raw_schema if isinstance(raw_schema, dict) else {}
            location = f"parameters[{pindex}]"
            if parameter.get("required"):
                add("required_field", name, op, location, "openapi_required_flag", "direct", 1.0)
            _schema_facts(add, op, schema, location + ".schema", name)
            if name.lower() in IDENTIFIER_NAMES or name.lower().endswith("_id"):
                add(
                    "identifier_field",
                    name,
                    op,
                    location + ".name",
                    "identifier_name_pattern",
                    strength=0.65,
                )
        request_body = op.get("request_body", {})
        content = request_body.get("content", {}) if isinstance(request_body, dict) else {}
        media = content.get("application/json", {}) if isinstance(content, dict) else {}
        schema = media.get("schema", {}) if isinstance(media, dict) else {}
        _walk_schema(add, op, schema, "request_body.schema", "")
        for status, response in (op.get("responses", {}) or {}).items():
            if isinstance(response, dict):
                add(
                    "response_status",
                    status,
                    op,
                    f"responses.{status}",
                    "declared_openapi_response",
                    "direct",
                    1.0,
                )
                response_content = response.get("content", {})
                response_media = (
                    response_content.get("application/json", {})
                    if isinstance(response_content, dict)
                    else {}
                )
                response_schema = (
                    response_media.get("schema", {}) if isinstance(response_media, dict) else {}
                )
                _walk_schema(
                    add,
                    op,
                    response_schema,
                    f"responses.{status}.content.application/json.schema",
                    "",
                )

    by_resource: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for op in operations:
        resource = next(
            (
                part
                for part in str(op.get("path", "")).split("/")
                if part and not part.startswith("{")
            ),
            "",
        )
        if resource:
            by_resource[resource.rstrip("s")].append(op)
    for resource, resource_ops in by_resource.items():
        intent_ops: dict[str, list[str]] = defaultdict(list)
        for op in resource_ops:
            method = str(op.get("method", "")).upper()
            crud_intent = {
                "POST": "create",
                "GET": "read",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }.get(method)
            operation_id_value = op.get("id")
            if crud_intent and isinstance(operation_id_value, str):
                intent_ops[crud_intent].append(operation_id_value)
        if len(intent_ops) > 1:
            for op in resource_ops:
                add(
                    "crud_relationship",
                    {"resource": resource, "available_intents": sorted(intent_ops)},
                    op,
                    "specification.operations",
                    "same_static_resource_and_http_methods",
                    strength=0.75,
                )
            creators = intent_ops.get("create", [])
            lifecycle = [
                op_id
                for intent in ("read", "update", "delete")
                for op_id in intent_ops.get(intent, [])
            ]
            if creators and lifecycle:
                for op in resource_ops:
                    if op.get("id") in lifecycle:
                        add(
                            "operation_dependency",
                            {"resource": resource, "predecessor_operation_ids": creators},
                            op,
                            "specification.operations",
                            "same_static_resource_create_precedes_lifecycle_operation",
                            strength=0.6,
                        )

    return facts


def _schema_facts(
    add: Any, op: dict[str, Any], schema: dict[str, Any], location: str, name: str
) -> None:
    _walk_schema(add, op, schema, location, name)


def _walk_schema(
    add: Any, op: dict[str, Any], schema: Any, location: str, field: str, depth: int = 0
) -> None:
    if not isinstance(schema, dict) or depth > 10:
        return
    if "$ref" in schema:
        add(
            "schema_reference",
            schema["$ref"],
            op,
            location + ".$ref",
            "local_reference_observed",
            "direct",
            1.0,
        )
        return
    if field:
        add(
            "field_semantics",
            {
                "name": field,
                "type": schema.get("type"),
                "format": schema.get("format"),
                "description": schema.get("description"),
                "enum": schema.get("enum"),
            },
            op,
            location,
            "schema_property_name_type_format_enum",
            "direct",
            0.95,
        )
        for key in CONSTRAINT_KEYS:
            if key in schema:
                add(
                    "field_constraint",
                    {"field": field, "constraint": key, "value": schema[key]},
                    op,
                    f"{location}.{key}",
                    "openapi_schema_constraint",
                    "direct",
                    1.0,
                )
        minimum = schema.get("minimum", schema.get("minLength"))
        maximum = schema.get("maximum", schema.get("maxLength"))
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum > maximum
        ):
            add(
                "constraint_conflict",
                {"field": field, "minimum": minimum, "maximum": maximum},
                op,
                location,
                "declared_minimum_exceeds_declared_maximum",
                strength=1.0,
            )
    required = schema.get("required")
    if isinstance(required, list):
        for name in required:
            add(
                "required_field",
                name,
                op,
                location + ".required",
                "openapi_required_list",
                "direct",
                1.0,
            )
    props = schema.get("properties")
    if isinstance(props, dict):
        for name, child in props.items():
            _walk_schema(add, op, child, f"{location}.properties.{name}", str(name), depth + 1)
    items = schema.get("items")
    if isinstance(items, dict):
        _walk_schema(add, op, items, location + ".items", field + "[]", depth + 1)


def candidate_semantic_score(
    candidate: dict[str, Any], operation: dict[str, Any], facts: list[dict[str, Any]]
) -> tuple[float, dict[str, float]]:
    kind = str(candidate.get("kind", ""))
    mutation = candidate.get("mutation", {})
    field_name = ""
    if isinstance(mutation, dict):
        if "remove_property" in mutation:
            field_name = str(mutation["remove_property"])
        elif "remove_parameter" in mutation:
            field_name = str(mutation["remove_parameter"].get("name", ""))
        elif "set_parameter" in mutation:
            field_name = str(mutation["set_parameter"].get("name", ""))
        elif mutation:
            field_name = str(next(iter(mutation)))
    contributions = {
        "contract_coverage": 1.0,
        "operation_intent": 0.0,
        "resource_workflow": 0.0,
        "field_semantics": 0.0,
    }
    for fact in facts:
        if fact.get("source_operation") != operation.get("id"):
            continue
        value = fact.get("value")
        if fact.get("fact_type") == "operation_intent":
            intent = value
            if (intent in {"create", "update"} and "required" in kind) or (
                intent == "delete" and "parameter" in kind
            ):
                contributions["operation_intent"] = max(contributions["operation_intent"], 1.25)
        if fact.get("fact_type") in {"crud_relationship", "operation_dependency"}:
            contributions["resource_workflow"] = max(contributions["resource_workflow"], 0.5)
        if (
            fact.get("fact_type") == "field_constraint"
            and isinstance(value, dict)
            and value.get("field") == field_name
        ):
            constraint_weight = (
                2.25 if any(token in kind for token in ("boundary", "enum")) else 0.5
            )
            contributions["field_semantics"] = max(
                contributions["field_semantics"], constraint_weight
            )
        if (
            fact.get("fact_type") == "field_semantics"
            and isinstance(value, dict)
            and value.get("name", "").lower() == field_name.lower()
        ):
            if value.get("format") or value.get("enum"):
                contributions["field_semantics"] = max(contributions["field_semantics"], 0.75)
    return sum(contributions.values()), contributions
