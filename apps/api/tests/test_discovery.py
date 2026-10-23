import json
from typing import Any

import pytest

from app.modules.api_understanding import discovery


def response(body: Any, content_type: str = "application/json") -> dict[str, Any]:
    return {
        "status_code": 200,
        "headers": {"content-type": content_type},
        "body": body,
    }


@pytest.mark.anyio
async def test_swagger_ui_discovers_non_default_yaml_spec_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute_request(**kwargs: Any) -> dict[str, Any]:
        url = kwargs["url"]
        if url.endswith("/docs"):
            return response(
                '<html><script>SwaggerUIBundle({url: "/contracts/current.yaml"})</script></html>',
                "text/html",
            )
        if url.endswith("/contracts/current.yaml"):
            return response(
                "openapi: 3.1.0\ninfo:\n  title: Custom docs API\n  version: '1'\n"
                "paths:\n  /ping:\n    get:\n      operationId: ping\n",
                "application/yaml",
            )
        return {"status_code": 404, "headers": {}, "body": ""}

    monkeypatch.setattr(discovery, "execute_request", fake_execute_request)
    result = await discovery.discover_specifications("https://api.example.test/docs")
    assert result["classification"] == "docs_ui"
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["source_url"].endswith("/contracts/current.yaml")
    assert result["candidates"][0]["specification"]["title"] == "Custom docs API"
    assert result["candidates"][0]["operations"][0]["operation_id"] == "ping"


@pytest.mark.anyio
async def test_config_url_and_multiple_spec_choices_are_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = {
        "/swagger-config": json.dumps(
            {"urls": [{"name": "One", "url": "/one.json"}, {"name": "Two", "url": "/two.json"}]}
        ).encode(),
        "/one.json": json.dumps(
            {"openapi": "3.1.0", "info": {"title": "One", "version": "1"}, "paths": {}}
        ).encode(),
        "/two.json": json.dumps(
            {"openapi": "3.1.0", "info": {"title": "Two", "version": "1"}, "paths": {}}
        ).encode(),
    }

    async def fake_execute_request(**kwargs: Any) -> dict[str, Any]:
        url = kwargs["url"]
        if url.endswith("/docs"):
            return response(
                '<script>SwaggerUIBundle({configUrl: "/swagger-config"})</script>',
                "text/html",
            )
        if url.endswith("/swagger-config"):
            return response(
                {"urls": [{"name": "One", "url": "/one.json"}, {"name": "Two", "url": "/two.json"}]}
            )
        for path, body in documents.items():
            if url.endswith(path):
                return response(json.loads(body))
        return {"status_code": 404, "headers": {}, "body": ""}

    monkeypatch.setattr(discovery, "execute_request", fake_execute_request)
    result = await discovery.discover_specifications("https://api.example.test/docs")
    assert result["ambiguous"] is True
    assert {candidate["specification"]["title"] for candidate in result["candidates"]} == {
        "One",
        "Two",
    }
