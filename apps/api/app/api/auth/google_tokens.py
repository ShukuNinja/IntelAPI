from typing import Any

from fastapi import HTTPException, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.core.config import get_settings


def verify_google_id_token(raw_token: str) -> dict[str, Any]:
    """Verify a Google ID token and return trusted identity claims."""

    settings = get_settings()

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AUTH_PROVIDER_NOT_CONFIGURED",
                "message": "Google authentication is not configured.",
            },
        )

    try:
        claims = id_token.verify_oauth2_token(
            raw_token,
            Request(),
            audience=settings.google_client_id,
        )
    except ValueError as exc:
        # Invalid signature, audience, expiry, issuer, or token claims.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_GOOGLE_TOKEN",
                "message": "The Google ID token is invalid or expired.",
            },
        ) from exc
    except GoogleAuthError as exc:
        # Verification infrastructure failed; do not misreport this
        # as proof that the supplied token is invalid.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AUTH_PROVIDER_UNAVAILABLE",
                "message": "Google token verification is temporarily unavailable.",
            },
        ) from exc

    # Never identify users using an email address.
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_GOOGLE_TOKEN",
                "message": "The Google ID token has no valid subject.",
            },
        )

    return claims
