"""Bounded remote OpenAPI and Swagger UI discovery using the shared executor."""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import yaml

from app.modules.api_understanding.service import (
    SpecificationError,
    parse_specification,
)
from app.modules.execution.service import ExecutionError, execute_request

MAX_DISCOVERY_ATTEMPTS = 12
FALLBACK_SPEC_PATHS = (
    "/openapi.json",
    "/openapi.yaml",
    "/swagger.json",
    "/swagger/v1/swagger.json",
    "/v3/api-docs",
    "/api-json",
    "/openapi/v1.json",
)


def _redact_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    authority = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


def _classify(url: str) -> str:
    name = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    if (
        name in {"openapi.json", "openapi.yaml", "openapi.yml", "swagger.json"}
        or "swagger.json" in name
    ):
        return "direct_spec"
    return "base_url"


def _config_spec_urls(config: object, config_url: str) -> list[str]:
    if not isinstance(config, dict):
        return []
    urls: list[str] = []
    one = config.get("url")
    if isinstance(one, str):
        urls.append(urljoin(config_url, one))
    many = config.get("urls")
    if isinstance(many, list):
        for entry in many:
            if isinstance(entry, dict) and isinstance(entry.get("url"), str):
                urls.append(urljoin(config_url, entry["url"]))
    return list(dict.fromkeys(urls))


def _html_config_urls(html: str, page_url: str) -> tuple[str | None, list[str]]:
    config_match = re.search(r"configUrl\s*:\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    config_url = urljoin(page_url, config_match.group(1)) if config_match else None
    urls: list[str] = []
    for match in re.finditer(r"(?:^|[,\s{])url\s*:\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE):
        urls.append(urljoin(page_url, match.group(1)))
    for match in re.finditer(r"data-url\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE):
        urls.append(urljoin(page_url, match.group(1)))
    return config_url, list(dict.fromkeys(urls))


def _parse_candidate(body: object, content_type: str, url: str) -> tuple[dict, dict] | None:
    source_format = (
        "yaml"
        if (
            urlsplit(url).path.lower().endswith((".yaml", ".yml")) or "yaml" in content_type.lower()
        )
        else "json"
    )
    document: object
    if isinstance(body, dict):
        document = body
    elif isinstance(body, str):
        try:
            document = json.loads(body)
            source_format = "json"
        except json.JSONDecodeError:
            try:
                document = yaml.safe_load(body)
                source_format = "yaml"
            except yaml.YAMLError as exc:
                raise SpecificationError("The response is neither valid JSON nor YAML.") from exc
    else:
        raise SpecificationError("The response body is not a JSON or YAML document.")
    if not isinstance(document, dict):
        raise SpecificationError("The specification root must be an object.")
    # YAML permits date-like scalars that are not JSON serializable; normalize
    # extensions and examples before returning data to the API and database.
    document = json.loads(json.dumps(document, default=str))
    normalized = parse_specification(document)
    return normalized, {"source_format": source_format, "document": document}


async def discover_specifications(input_url: str) -> dict:
    parsed = urlsplit(input_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Provide an absolute HTTP or HTTPS URL without embedded credentials.")
    initial_kind = _classify(input_url)
    attempts: list[dict] = []
    candidates: list[dict] = []
    visited: set[str] = set()

    async def fetch(target_url: str) -> tuple[object | None, str, dict | None]:
        if target_url in visited or len(attempts) >= MAX_DISCOVERY_ATTEMPTS:
            return None, "", None
        visited.add(target_url)
        record: dict = {"url": _redact_url(target_url), "status_code": None, "result": "not_a_spec"}
        attempts.append(record)
        try:
            response = await execute_request(
                method="GET",
                url=target_url,
                headers={
                    "Accept": "application/json, application/yaml, text/yaml, text/html;q=0.8"
                },
                body=None,
                confirm_unsafe=False,
            )
        except ExecutionError:
            record["result"] = "blocked_or_unavailable"
            record["error"] = "Target was blocked by network policy or could not be reached."
            return None, "", None
        record["status_code"] = response["status_code"]
        if response["status_code"] < 200 or response["status_code"] >= 300:
            record["result"] = "http_error"
            return None, response["headers"].get("content-type", ""), response
        record["result"] = "fetched"
        return response["body"], response["headers"].get("content-type", ""), response

    async def inspect(target_url: str) -> tuple[bool, str | None]:
        body, content_type, response = await fetch(target_url)
        if response is None or body is None:
            return False, None
        is_html = "html" in content_type.lower() or (
            isinstance(body, str) and "<html" in body[:1000].lower()
        )
        if is_html:
            attempts[-1]["result"] = "docs_ui"
            return False, body if isinstance(body, str) else None
        try:
            parsed_candidate = _parse_candidate(body, content_type, target_url)
        except (SpecificationError, ValueError) as exc:
            attempts[-1]["result"] = "invalid_spec"
            attempts[-1]["error"] = str(exc)
            return False, None
        if parsed_candidate is None:
            return False, None
        normalized, source = parsed_candidate
        candidates.append(
            {
                "source_url": _redact_url(target_url),
                "specification": normalized["specification"],
                "operation_count": len(normalized["operations"]),
                "operations": normalized["operations"],
                "source_format": source["source_format"],
                "document": source["document"],
            }
        )
        attempts[-1]["result"] = "valid_spec"
        return True, None

    async with asyncio.timeout(60):
        is_spec, html = await inspect(input_url)
        if is_spec:
            return {
                "input_url": _redact_url(input_url),
                "classification": "direct_spec",
                "attempts": attempts,
                "candidates": candidates,
            }

        config_url: str | None = None
        configured_urls: list[str] = []
        if html is not None:
            config_url, configured_urls = _html_config_urls(html, input_url)
        if config_url is not None and len(attempts) < MAX_DISCOVERY_ATTEMPTS:
            config_body, config_type, config_response = await fetch(config_url)
            if config_response is not None and config_response["status_code"] < 300:
                if isinstance(config_body, str):
                    try:
                        config_body = json.loads(config_body)
                    except json.JSONDecodeError:
                        config_body = None
                configured_urls.extend(_config_spec_urls(config_body, config_url))

        if html is not None:
            configured_urls.extend(urljoin(input_url, path) for path in FALLBACK_SPEC_PATHS)
        else:
            base = f"{parsed.scheme}://{parsed.netloc}/"
            configured_urls.extend(urljoin(base, path.lstrip("/")) for path in FALLBACK_SPEC_PATHS)

        for target_url in dict.fromkeys(configured_urls):
            if len(attempts) >= MAX_DISCOVERY_ATTEMPTS:
                break
            await inspect(target_url)

    classification = "docs_ui" if html is not None else initial_kind
    return {
        "input_url": _redact_url(input_url),
        "classification": classification,
        "attempts": attempts,
        "candidates": candidates,
        "ambiguous": len(candidates) > 1,
    }
