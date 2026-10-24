"""Bounded HTTP request execution and target validation."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings

MAX_REQUEST_BODY_BYTES = 1_000_000
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ExecutionError(ValueError):
    """A request cannot be safely executed or completed."""

    def __init__(self, message: str, outcome: str = "blocked_by_policy") -> None:
        super().__init__(message)
        self.outcome = outcome


def validate_url_syntax(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ExecutionError("The request URL is invalid.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ExecutionError("Only absolute HTTP and HTTPS URLs are supported.")
    if parsed.username is not None or parsed.password is not None:
        raise ExecutionError("Credentials in request URLs are not allowed; use the auth headers.")
    if parsed.fragment:
        raise ExecutionError("Request URLs cannot include a fragment.")
    host_part = parsed.hostname.lower()
    if ":" in host_part:
        host_part = f"[{host_part}]"
    origin = f"{parsed.scheme}://{host_part}"
    if port is not None:
        origin += f":{port}"
    return parsed.hostname.rstrip(".").lower(), origin


def _check_address(address: str) -> None:
    settings = get_settings()
    try:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
    except ValueError as exc:
        raise ExecutionError("The target resolved to an invalid network address.") from exc
    if ip.is_loopback:
        if not settings.allow_local_targets:
            raise ExecutionError("Local API targets are disabled by server policy.")
        return
    if not ip.is_global and not settings.allow_private_network_targets:
        raise ExecutionError("The target resolves to a private or reserved network address.")


def _resolve_and_validate(hostname: str) -> list[str]:
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        if hostname == "localhost":
            addresses = ["127.0.0.1", "::1"]
        else:
            try:
                records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise ExecutionError("The target hostname could not be resolved.") from exc
            addresses = list({record[4][0] for record in records})
    else:
        addresses = [str(literal)]
    if not addresses:
        raise ExecutionError("The target hostname did not resolve to an address.")
    for address in addresses:
        _check_address(address)
    return addresses


async def execute_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: str | None,
    confirm_unsafe: bool,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    method = method.upper()
    if method not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
        raise ExecutionError("The HTTP method is not supported.")
    if method not in SAFE_METHODS and not confirm_unsafe:
        raise ExecutionError("Confirm this state-changing request before sending it.")
    if body is not None and len(body.encode("utf-8")) > MAX_REQUEST_BODY_BYTES:
        raise ExecutionError("Request body exceeds the 1 MB limit.")
    if len(headers) > 100:
        raise ExecutionError("A request can include at most 100 headers.")

    hostname, origin = validate_url_syntax(url)
    addresses = await resolve_and_validate(hostname)
    parsed = urlsplit(url)
    port = parsed.port
    address = addresses[0]
    url_host = f"[{address}]" if ":" in address else address
    authority = f"{url_host}:{port}" if port is not None else url_host
    pinned_url = parsed._replace(netloc=authority).geturl()
    request_headers = {key: value for key, value in headers.items() if key.lower() != "host"}
    host_header = hostname
    if ":" in host_header and not host_header.startswith("["):
        host_header = f"[{host_header}]"
    request_headers["Host"] = f"{host_header}:{port}" if port is not None else host_header
    settings = get_settings()
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout_seconds,
        read=settings.http_read_timeout_seconds,
        write=settings.http_read_timeout_seconds,
        pool=settings.http_connect_timeout_seconds,
    )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            request = client.build_request(
                method, pinned_url, headers=request_headers, content=body
            )
            if parsed.scheme == "https":
                request.extensions["sni_hostname"] = hostname
            response = await client.send(request, stream=True)
            try:
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > settings.http_max_response_bytes:
                        raise ExecutionError(
                            "Response exceeds the configured size limit.", "response_too_large"
                        )
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                response_body: object
                content_type = response.headers.get("content-type", "")
                if "json" in content_type.lower():
                    try:
                        response_body = json.loads(raw_body)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        response_body = raw_body.decode("utf-8", errors="replace")
                else:
                    response_body = raw_body.decode("utf-8", errors="replace")
                safe_headers = {
                    key: response.headers[key]
                    for key in ("content-type", "content-length", "date")
                    if key in response.headers
                }
                return {
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "response_bytes": size,
                    "headers": safe_headers,
                    "body": response_body,
                    "origin": origin,
                    "outcome": "http_response",
                }
            finally:
                await response.aclose()
    except ExecutionError:
        raise
    except httpx.TimeoutException as exc:
        raise ExecutionError("The target request timed out.", "timeout") from exc
    except httpx.HTTPError as exc:
        raise ExecutionError(
            "The target request could not be completed.", "connection_error"
        ) from exc


async def resolve_and_validate(hostname: str) -> list[str]:
    """Run blocking DNS checks outside of the event loop."""
    return await asyncio.to_thread(_resolve_and_validate, hostname)
