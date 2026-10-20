from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError

from app.api.auth import google_tokens


def configure_google_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        google_tokens,
        "get_settings",
        lambda: SimpleNamespace(google_client_id="test-client-id"),
    )


def test_missing_google_client_id_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        google_tokens,
        "get_settings",
        lambda: SimpleNamespace(google_client_id=""),
    )

    with pytest.raises(HTTPException) as exc_info:
        google_tokens.verify_google_id_token("any-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"


def test_valid_token_returns_verified_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_google_client(monkeypatch)
    expected_claims = {
        "sub": "google-user-123",
        "email": "user@example.com",
        "iss": "https://accounts.google.com",
    }

    def fake_verify(
        raw_token: str,
        request: object,
        audience: str,
    ) -> dict[str, str]:
        assert raw_token == "test-token"
        assert audience == "test-client-id"
        return expected_claims

    monkeypatch.setattr(
        google_tokens.id_token,
        "verify_oauth2_token",
        fake_verify,
    )

    claims = google_tokens.verify_google_id_token("test-token")

    assert claims == expected_claims
    assert claims["sub"] == "google-user-123"


def test_invalid_token_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_google_client(monkeypatch)
    monkeypatch.setattr(
        google_tokens.id_token,
        "verify_oauth2_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid token")),
    )

    with pytest.raises(HTTPException) as exc_info:
        google_tokens.verify_google_id_token("invalid-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INVALID_GOOGLE_TOKEN"


def test_google_verification_outage_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_google_client(monkeypatch)
    monkeypatch.setattr(
        google_tokens.id_token,
        "verify_oauth2_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(GoogleAuthError("verification unavailable")),
    )

    with pytest.raises(HTTPException) as exc_info:
        google_tokens.verify_google_id_token("test-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "AUTH_PROVIDER_UNAVAILABLE"


def test_token_without_subject_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_google_client(monkeypatch)
    monkeypatch.setattr(
        google_tokens.id_token,
        "verify_oauth2_token",
        lambda *args, **kwargs: {"email": "user@example.com"},
    )

    with pytest.raises(HTTPException) as exc_info:
        google_tokens.verify_google_id_token("test-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INVALID_GOOGLE_TOKEN"
