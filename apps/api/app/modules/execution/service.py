import json
import re
import time
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret
from app.models.environment import Environment
from app.models.environment_variable import EnvironmentVariable
from app.models.execution import Execution
from app.models.project import Project
from app.models.saved_request import SavedRequest
from app.modules.evidence.service import build_execution_evidence
from app.modules.execution.security import validate_outbound_url

MAX_RESPONSE_BYTES = 1_048_576
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _fail(code: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _load_variables(
    db: Session, environment: Environment | None
) -> tuple[dict[str, str], list[str]]:
    if environment is None:
        return {}, []
    rows = db.scalars(
        select(EnvironmentVariable).where(EnvironmentVariable.environment_id == environment.id)
    ).all()
    values: dict[str, str] = {}
    secrets: list[str] = []
    for row in rows:
        if row.is_secret:
            value = decrypt_secret(row.value_ciphertext or b"")
            secrets.append(value)
        else:
            value = row.value_plain or ""
        values[row.key] = value
    if environment.base_url:
        values["base_url"] = environment.base_url.rstrip("/")
    return values, [value for value in secrets if value]


def _substitute(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        missing: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                missing.add(key)
                return match.group(0)
            return variables[key]

        result = PLACEHOLDER.sub(replace, value)
        if missing:
            raise _fail(
                "MISSING_VARIABLE",
                f"Unresolved environment variables: {', '.join(sorted(missing))}.",
            )
        return result
    if isinstance(value, list):
        return [_substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {str(key): _substitute(item, variables) for key, item in value.items()}
    return value


def _redact(value: str | None, secrets: list[str]) -> str | None:
    if value is None:
        return None
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def _build_url(template: str, environment: Environment | None, variables: dict[str, str]) -> str:
    if "{{base_url}}" in template and "base_url" not in variables:
        raise _fail("MISSING_BASE_URL", "The selected environment does not define a base URL.")
    resolved = _substitute(template, variables)
    if not isinstance(resolved, str):
        raise _fail("INVALID_URL", "The resolved request URL must be a string.")
    if resolved.startswith("/"):
        if environment is None or not environment.base_url:
            raise _fail("MISSING_BASE_URL", "A relative URL requires an environment base URL.")
        resolved = urljoin(environment.base_url.rstrip("/") + "/", resolved.lstrip("/"))
    return resolved


def _headers(raw: dict[str, Any]) -> dict[str, str]:
    blocked = {"host", "content-length", "connection", "transfer-encoding", "proxy-authorization"}
    result: dict[str, str] = {}
    for key, value in raw.items():
        if key.lower() in blocked:
            continue
        if not isinstance(value, (str, int, float, bool)):
            raise _fail("INVALID_HEADER", f"Header {key!r} must have a scalar value.")
        result[str(key)] = str(value)
    return result


def execute_saved_request(
    db: Session,
    saved_request: SavedRequest,
    owner_user_id: object,
    environment_override_id: object | None,
    timeout_seconds: float,
) -> Execution:
    project = db.scalar(
        select(Project).where(
            Project.id == saved_request.project_id,
            Project.owner_user_id == owner_user_id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise _fail("NOT_FOUND", "Saved request not found.", 404)
    selected_id = environment_override_id or saved_request.environment_id
    environment: Environment | None = None
    if selected_id is not None:
        environment = db.scalar(
            select(Environment).where(
                Environment.id == selected_id, Environment.project_id == saved_request.project_id
            )
        )
        if environment is None:
            raise _fail("INVALID_ENVIRONMENT", "Environment must belong to the request's project.")
    variables, secret_values = _load_variables(db, environment)
    url = _build_url(saved_request.url_template, environment, variables)
    validate_outbound_url(url)
    headers = _headers(_substitute(saved_request.headers or {}, variables))
    params = _substitute(saved_request.query_params or {}, variables)
    body = _substitute(saved_request.body, variables)
    content: bytes | None = None
    if saved_request.body_type == "json":
        content = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif saved_request.body_type == "text":
        content = str(body if body is not None else "").encode("utf-8")
    elif saved_request.body_type == "form_urlencoded":
        if not isinstance(body, dict):
            raise _fail("INVALID_BODY", "Form URL-encoded body must be an object.")
        content = urlencode(body, doseq=True).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif saved_request.body_type == "multipart":
        raise _fail(
            "UNSUPPORTED_BODY_TYPE", "Multipart bodies are not supported by this execution version."
        )
    elif saved_request.body_type != "none":
        raise _fail("INVALID_BODY_TYPE", "The saved request has an unsupported body type.")

    started = time.monotonic()
    execution = Execution(
        project_id=saved_request.project_id,
        saved_request_id=saved_request.id,
        environment_id=environment.id if environment else None,
        status="failed",
        method=saved_request.method.upper(),
        url=_redact(url, secret_values) or url,
        response_headers={},
    )
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "IntelAPI/0.1"},
        ) as client:
            with client.stream(
                execution.method, url, params=params, headers=headers, content=content
            ) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise _fail(
                            "RESPONSE_TOO_LARGE", "Response exceeded the 1 MiB response limit.", 413
                        )
                response_text = raw.decode(response.encoding or "utf-8", errors="replace")
                execution.status = "completed"
                execution.response_status_code = response.status_code
                execution.response_headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower()
                    in {"content-type", "content-length", "date", "server", "retry-after"}
                }
                execution.response_body = _redact(response_text, secret_values)
                execution.duration_ms = round((time.monotonic() - started) * 1000)
    except HTTPException:
        raise
    except httpx.TimeoutException:
        execution.error_code = "TIMEOUT"
        execution.error_message = "The outbound request timed out."
        execution.duration_ms = round((time.monotonic() - started) * 1000)
    except httpx.RequestError:
        execution.error_code = "NETWORK_ERROR"
        execution.error_message = "The outbound request failed before a response was received."
        execution.duration_ms = round((time.monotonic() - started) * 1000)
    db.add(execution)
    db.flush()
    execution.evidence.extend(build_execution_evidence(execution))
    db.commit()
    db.refresh(execution)
    return execution