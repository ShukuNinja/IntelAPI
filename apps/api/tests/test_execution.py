import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest

from app.core.config import get_settings
from app.modules.execution.service import ExecutionError, execute_request


@pytest.mark.anyio
async def test_request_executes_and_returns_real_response_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/health"
        assert request.url.host == "127.0.0.1"
        assert request.headers["host"] == "localhost:8000"
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "set-cookie": "private=secret"},
            json={"healthy": True},
        )

    result = await execute_request(
        method="GET",
        url="http://localhost:8000/health",
        headers={},
        body=None,
        confirm_unsafe=False,
        transport=httpx.MockTransport(handler),
    )
    assert result["status_code"] == 200
    assert result["body"] == {"healthy": True}
    assert "set-cookie" not in result["headers"]
    assert result["origin"] == "http://localhost:8000"


@pytest.mark.anyio
async def test_state_changing_request_requires_confirmation() -> None:
    with pytest.raises(ExecutionError, match="Confirm"):
        await execute_request(
            method="DELETE",
            url="http://localhost/resource",
            headers={},
            body=None,
            confirm_unsafe=False,
            transport=httpx.MockTransport(lambda request: httpx.Response(204)),
        )


@pytest.mark.anyio
async def test_private_network_target_is_blocked_by_default() -> None:
    with pytest.raises(ExecutionError, match="private or reserved"):
        await execute_request(
            method="GET",
            url="http://192.168.1.10/",
            headers={},
            body=None,
            confirm_unsafe=False,
            transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        )


@pytest.mark.anyio
async def test_embedded_url_credentials_are_rejected() -> None:
    with pytest.raises(ExecutionError, match="Credentials"):
        await execute_request(
            method="GET",
            url="http://user:pass@localhost/",
            headers={},
            body=None,
            confirm_unsafe=False,
            transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        )


@pytest.mark.anyio
async def test_redirect_is_reported_without_following_target() -> None:
    visited: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        visited.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1:9999/internal"})

    result = await execute_request(
        method="GET",
        url="http://localhost:8000/start",
        headers={},
        body=None,
        confirm_unsafe=False,
        transport=httpx.MockTransport(handler),
    )
    assert result["status_code"] == 302
    assert visited == ["http://127.0.0.1:8000/start"]


@pytest.mark.anyio
async def test_https_connects_to_validated_ip_while_preserving_host_and_sni() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert request.headers["host"] == "localhost:8443"
        assert request.extensions["sni_hostname"] == "localhost"
        return httpx.Response(204)

    result = await execute_request(
        method="GET",
        url="https://localhost:8443/check",
        headers={},
        body=None,
        confirm_unsafe=False,
        transport=httpx.MockTransport(handler),
    )
    assert result["status_code"] == 204


@pytest.mark.anyio
async def test_localhost_fixture_is_reached_over_real_http() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"fixture": "reachable", "path": self.path}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        result = await execute_request(
            method="GET",
            url=f"http://localhost:{port}/health",
            headers={},
            body=None,
            confirm_unsafe=False,
        )
        assert result["status_code"] == 200
        assert result["body"] == {"fixture": "reachable", "path": "/health"}
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.anyio
async def test_response_size_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "http_max_response_bytes", 5)
    with pytest.raises(ExecutionError, match="size limit") as error:
        await execute_request(
            method="GET",
            url="http://localhost/resource",
            headers={},
            body=None,
            confirm_unsafe=False,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"123456")),
        )
    assert error.value.outcome == "response_too_large"
