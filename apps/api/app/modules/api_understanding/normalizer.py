"""Deterministic extraction of operations from parsed OpenAPI documents."""

from typing import Any

from app.modules.api_understanding.errors import OpenAPIValidationError
from app.modules.api_understanding.models import NormalizedOperation, SourceReference

HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


def _resolve_local_ref(document: dict[str, Any], reference: str) -> Any:
    """Resolve a local JSON Pointer reference without network access."""
    if not reference.startswith("#/"):
        raise OpenAPIValidationError(
            f"Only local JSON Pointer references are supported here: {reference!r}"
        )

    current: Any = document
    for raw_token in reference[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise OpenAPIValidationError(f"Unresolvable local reference: {reference!r}")
    return current


def _dereference_parameter(
    parameter: Any, document: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(parameter, dict):
        raise OpenAPIValidationError("Operation parameters must be objects")
    reference = parameter.get("$ref")
    if reference is None:
        return parameter
    resolved = _resolve_local_ref(document, reference)
    if not isinstance(resolved, dict):
        raise OpenAPIValidationError(f"Parameter reference {reference!r} must resolve to an object")
    return resolved

def _parameter_identity(parameter: dict[str, Any]) -> tuple[str, str]:
    """Return the OpenAPI parameter identity: (name, in)."""
    name = parameter.get("name")
    location = parameter.get("in")

    if not isinstance(name, str) or not name:
        raise OpenAPIValidationError(
            "Each parameter must define a non-empty 'name'"
        )
    if not isinstance(location, str) or not location:
        raise OpenAPIValidationError(
            "Each parameter must define a non-empty 'in'"
        )

    return name, location


def _merge_parameters(
    path_parameters: list[Any],
    operation_parameters: list[Any],
    document: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Merge path and operation parameters using OpenAPI override rules."""
    resolved_path = [
        _dereference_parameter(parameter, document)
        for parameter in path_parameters
    ]
    resolved_operation = [
        _dereference_parameter(parameter, document)
        for parameter in operation_parameters
    ]

    def index_parameters(
        parameters: list[dict[str, Any]],
        scope: str,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        indexed: dict[tuple[str, str], dict[str, Any]] = {}

        for parameter in parameters:
            identity = _parameter_identity(parameter)

            if identity in indexed:
                raise OpenAPIValidationError(
                    f"Duplicate {scope} parameter: "
                    f"{identity[0]!r} in {identity[1]!r}"
                )

            indexed[identity] = parameter

        return indexed

    path_index = index_parameters(resolved_path, "path-level")
    operation_index = index_parameters(
        resolved_operation,
        "operation-level",
    )

    merged = [
        parameter
        for identity, parameter in path_index.items()
        if identity not in operation_index
    ]
    merged.extend(resolved_operation)

    return tuple(merged)

def normalize_operations(
    document: dict[str, Any],
) -> tuple[NormalizedOperation, ...]:
    """Extract HTTP operations in stable path/method order."""
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenAPIValidationError("'paths' must be an object")

    operations: list[NormalizedOperation] = []
    for path in sorted(paths):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            raise OpenAPIValidationError(f"Path item for {path!r} must be an object")

        path_parameters = path_item.get("parameters", [])
        if not isinstance(path_parameters, list):
            raise OpenAPIValidationError(f"Parameters for path {path!r} must be a list")

        for method in sorted(HTTP_METHODS):
            operation = path_item.get(method)
            if operation is None:
                continue
            if not isinstance(operation, dict):
                raise OpenAPIValidationError(f"Operation {method.upper()} {path} must be an object")

            operation_parameters = operation.get("parameters", [])
            if not isinstance(operation_parameters, list):
                raise OpenAPIValidationError(
                    f"Parameters for {method.upper()} {path} must be a list"
                )
            parameters = _merge_parameters(
                path_parameters,
                operation_parameters,
                document,
            )

            request_body = operation.get("requestBody")
            request_schema: dict[str, Any] | None = None
            if request_body is not None:
                if not isinstance(request_body, dict):
                    raise OpenAPIValidationError(
                        f"requestBody for {method.upper()} {path} must be an object"
                    )
                body_ref = request_body.get("$ref")
                if body_ref is not None:
                    request_body = _resolve_local_ref(document, body_ref)
                if not isinstance(request_body, dict):
                    raise OpenAPIValidationError("requestBody reference must resolve to an object")
                content = request_body.get("content", {})
                if not isinstance(content, dict):
                    raise OpenAPIValidationError("requestBody.content must be an object")
                for media_type in sorted(content):
                    media = content[media_type]
                    if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                        request_schema = media["schema"]
                        break

            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                raise OpenAPIValidationError(
                    f"Responses for {method.upper()} {path} must be an object"
                )
            response_schemas: dict[str, Any] = {}
            for status in sorted(responses):
                response = responses[status]
                if not isinstance(response, dict):
                    raise OpenAPIValidationError(
                        f"Response {status!r} for {method.upper()} {path} must be an object"
                    )
                response_ref = response.get("$ref")
                if response_ref is not None:
                    response = _resolve_local_ref(document, response_ref)
                if not isinstance(response, dict):
                    raise OpenAPIValidationError("Response reference must resolve to an object")
                content = response.get("content", {})
                if isinstance(content, dict):
                    for media_type in sorted(content):
                        media = content[media_type]
                        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                            response_schemas[f"{status}:{media_type}"] = media["schema"]

            security = operation.get("security", document.get("security", []))
            if not isinstance(security, list) or any(
                not isinstance(item, dict) for item in security
            ):
                raise OpenAPIValidationError(
                    f"Security requirements for {method.upper()} {path} must be a list of objects"
                )


            operations.append(
                NormalizedOperation(
                    operation_key=f"{method.upper()} {path}",
                    method=method.upper(),
                    path=path,
                    summary=operation.get("summary"),
                    operation_id=operation.get("operationId"),
                    parameters=parameters,
                    request_body_schema=request_schema,
                    response_schemas=response_schemas,
                    security_requirements=tuple(security),
                    source_ref=SourceReference(
                        pointer=f"#/paths/{path.replace('~', '~0').replace('/', '~1')}/{method}",
                    ),
                )
            )

    return tuple(operations)
