import hmac

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth.sessions import get_user_for_session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def auth_error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def validate_allowed_origin(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")

    if not origin or origin not in settings.cors_origins:
        raise auth_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "The request origin is not allowed.",
        )


def validate_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise auth_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "The CSRF token is missing or invalid.",
        )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    # Validate origin and CSRF on every protected state-changing request.
    if request.method not in SAFE_METHODS:
        validate_allowed_origin(request)
        validate_csrf(request)

    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)

    user = get_user_for_session(db, raw_token)

    if user is None:
        raise auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHENTICATED",
            "A valid application session is required.",
        )

    return user
