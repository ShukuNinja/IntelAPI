from app.modules.api_understanding.service import parse_specification
from app.modules.readiness.service import analyze_readiness


def test_readiness_reports_source_linked_completeness_findings() -> None:
    parsed = parse_specification(
        {
            "openapi": "3.1.0",
            "info": {"title": "Orders", "version": "1"},
            "paths": {
                "/orders/{order_id}": {
                    "get": {"parameters": [{"name": "order_id", "in": "path", "required": True}]}
                }
            },
        }
    )

    report = analyze_readiness(
        {
            "paths": {"/orders/{order_id}": {"get": {}}},
            "servers": [],
        },
        parsed["operations"],
    )

    codes = {finding["code"] for finding in report["findings"]}
    assert {"missing_summary", "missing_operation_id", "missing_responses"} <= codes
    assert "parameter_schema_missing" in codes
    assert "server_url_missing" in codes
    assert all(
        finding["evidence"]["json_pointer"].startswith("/") for finding in report["findings"]
    )
    parameter_finding = next(
        item for item in report["findings"] if item["code"] == "parameter_schema_missing"
    )
    assert parameter_finding["evidence"]["json_pointer"] == (
        "/paths/~1orders~1{order_id}/get/parameters/0"
    )
    assert report["summary"]["operations_needing_attention"] == 1
    assert report["scope"] == "documented_completeness_only"


def test_readiness_does_not_flag_a_complete_operation() -> None:
    parsed = parse_specification(
        {
            "openapi": "3.1.0",
            "info": {"title": "Health", "version": "1"},
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/health": {
                    "get": {
                        "operationId": "health",
                        "summary": "Health check",
                        "responses": {"200": {"description": "Healthy"}},
                    }
                }
            },
        }
    )
    report = analyze_readiness(
        {
            "servers": [{"url": "https://api.example.test"}],
            "paths": {"/health": {"get": {}}},
        },
        parsed["operations"],
    )
    assert report["findings"] == []
    assert report["operations"][0]["readiness"] == "ready"
