"""Safe, bounded parsing of OpenAPI JSON and YAML documents."""

import json
from typing import Any

import yaml

from app.modules.api_understanding.errors import (
    OpenAPIParseError,
    OpenAPIReferenceError,
    OpenAPIValidationError,
    UnsupportedOpenAPIVersionError,
)

DEFAULT_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
SUPPORTED_VERSIONS = ("3.0.", "3.1.")


def _reject_remote_refs(value: Any, pointer: str = "#") -> None:
    """Reject remote references recursively; never perform network access."""
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#"):
            raise OpenAPIReferenceError(
                f"Remote reference at {pointer}/$ref is unsupported: {reference!r}"
            )
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            _reject_remote_refs(child, f"{pointer}/{escaped}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_remote_refs(child, f"{pointer}/{index}")


def parse_openapi_document(
    content: str | bytes,
    *,
    max_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
) -> dict[str, Any]:
    """Parse and structurally validate an OpenAPI 3.0 or 3.1 document."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    raw = content.encode("utf-8") if isinstance(content, str) else content
    if len(raw) > max_bytes:
        raise OpenAPIValidationError(
            f"Document is too large ({len(raw)} bytes; limit is {max_bytes} bytes)"
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OpenAPIParseError("Document must be UTF-8 encoded") from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OpenAPIParseError("Document is neither valid JSON nor valid YAML") from exc
    except RecursionError as exc:
        raise OpenAPIParseError("Document nesting is too deep") from exc

    if not isinstance(document, dict):
        raise OpenAPIValidationError("OpenAPI document root must be an object")

    version = document.get("openapi")
    if not isinstance(version, str):
        raise OpenAPIValidationError("Required field 'openapi' must be a string")
    if not version.startswith(SUPPORTED_VERSIONS):
        raise UnsupportedOpenAPIVersionError(
            f"Unsupported OpenAPI version {version!r}; supported families are 3.0.x and 3.1.x"
        )
    if not isinstance(document.get("info"), dict):
        raise OpenAPIValidationError("Required field 'info' must be an object")
    if not isinstance(document["info"].get("title"), str) or not document["info"]["title"]:
        raise OpenAPIValidationError("'info.title' must be a non-empty string")
    if not isinstance(document["info"].get("version"), str):
        raise OpenAPIValidationError("'info.version' must be a string")
    if not isinstance(document.get("paths", {}), dict):
        raise OpenAPIValidationError("'paths' must be an object")

    _reject_remote_refs(document)
    return document
