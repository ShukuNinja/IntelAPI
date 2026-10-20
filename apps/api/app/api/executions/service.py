import asyncio
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import httpx

from app.api.executions.schemas import ExecutionRequest, ExecutionResponse


REQUEST_TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB

# These headers describe hop-by-hop transport details or can expose cookies.
EXCLUDED_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "set-cookie",
    "set-cookie2",
}


class ExecutionError(Exception):
    """An outbound request could not be executed safely."""


def _validate_public_destination(url: str) -> None:
    """
    Reject non-HTTP(S) URLs and destinations resolving to non-public IPs.

    This is a preflight check, not a complete defense against DNS rebinding.
    Production deployments should also enforce outbound network restrictions.
    """
    parsed = urlsplit(url)

    if parsed.scheme not in {"http", "https"}:
        raise ExecutionError("Only HTTP and HTTPS URLs are supported.")

    hostname = parsed.hostname

    if not hostname:
        raise ExecutionError("The request URL must contain a hostname.")

    if parsed.username is not None or parsed.password is not None:
        raise ExecutionError("URLs containing embedded credentials are not allowed.")

    # Reject local hostnames and common local/internal DNS suffixes.
    normalized_hostname = hostname.rstrip(".").lower()

    blocked_hostnames = {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }

    if (
        normalized_hostname in blocked_hostnames
        or normalized_hostname.endswith(".localhost")
        or normalized_hostname.endswith(".local")
        or normalized_hostname.endswith(".internal")
    ):
        raise ExecutionError("Requests to local or internal hostnames are blocked.")

    try:
        # IP literals do not need DNS resolution.
        literal_ip = ipaddress.ip_address(normalized_hostname)
        addresses = [literal_ip]
    except ValueError:
        try:
            records = socket.getaddrinfo(
                normalized_hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise ExecutionError("The target hostname could not be resolved.") from exc

        addresses = [
            ipaddress.ip_address(record[4][0])
            for record in records
        ]

    if not addresses:
        raise ExecutionError("The target hostname did not resolve to an IP address.")

    # Reject the entire destination if any resolved address is non-public.
    for address in addresses:
        if not address.is_global:
            raise ExecutionError(
                "Requests to private, local, or otherwise non-public IP addresses "
                "are blocked."
            )


async def execute_request(
    request: ExecutionRequest,
) -> ExecutionResponse:
    """Execute a validated HTTP request with bounded time and response size."""

    target_url = str(request.url)

    # DNS lookup is blocking, so perform the preflight check in a worker thread.
    try:
        await asyncio.to_thread(_validate_public_destination, target_url)
    except ExecutionError:
        raise
    except Exception as exc:
        raise ExecutionError("The target URL failed destination validation.") from exc

    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)

    started_at = time.perf_counter()

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
            method=request.method,
            url=target_url,
            headers=request.headers,
            params=request.query_params or None,
            content=request.body,
            ) as response:
                body_chunks: list[bytes] = []
                size_bytes = 0

                async for chunk in response.aiter_bytes():
                    size_bytes += len(chunk)

                    if size_bytes > MAX_RESPONSE_BYTES:
                        raise ExecutionError(
                            "The response exceeded the 2 MiB size limit."
                        )

                    body_chunks.append(chunk)

                body_bytes = b"".join(body_chunks)

                # Decode using the response's declared encoding when possible.
                encoding = response.encoding or "utf-8"
                body_text = body_bytes.decode(encoding, errors="replace")

                response_headers = {
                    name: value
                    for name, value in response.headers.items()
                    if name.lower() not in EXCLUDED_RESPONSE_HEADERS
                }

                duration_ms = (time.perf_counter() - started_at) * 1000

                return ExecutionResponse(
                    status_code=response.status_code,
                    headers=response_headers,
                    body=body_text,
                    duration_ms=round(duration_ms, 2),
                    size_bytes=len(body_bytes),
                    final_url=str(response.url),
                )

    except ExecutionError:
        raise
    except httpx.TimeoutException as exc:
        raise ExecutionError("The target API request timed out.") from exc
    except httpx.RequestError as exc:
        raise ExecutionError(
            "The target API could not be reached or returned a network error."
        ) from exc