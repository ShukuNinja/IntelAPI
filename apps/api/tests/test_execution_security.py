import pytest
from fastapi import HTTPException

from app.modules.execution.security import validate_outbound_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1:8000/health",
        "http://localhost/admin",
        "http://sub.localhost/admin",
        "http://printer.local/",
        "http://service.internal/",
        "http://metadata.google.internal/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "https://user:pass@example.com/",
    ],
)
def test_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_outbound_url(url)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "UNSAFE_DESTINATION"


def test_rejects_relative_url() -> None:
    with pytest.raises(HTTPException):
        validate_outbound_url("/api/health")