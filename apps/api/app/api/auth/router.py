import secrets

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth.dependencies import (
    auth_error,
    get_current_user,
    validate_allowed_origin,
)
from app.api.auth.google_tokens import verify_google_id_token
from app.api.auth.schemas import GoogleConfigRead, GoogleSessionRequest, UserRead
from app.api.auth.sessions import create_session, revoke_session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


def _optional_claim(
    claims: dict,
    claim_name: str,
    max_length: int | None = None,
) -> str | None:
    value = claims.get(claim_name)
    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()
    return value[:max_length] if max_length else value


def _get_or_create_user(
    db: Session,
    claims: dict,
) -> User:
    subject = claims["sub"]

    if len(subject) > 255:
        raise auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_GOOGLE_TOKEN",
            "The Google identity subject is invalid.",
        )

    user = db.scalar(select(User).where(User.google_sub == subject))

    if user is None:
        user = User(
            google_sub=subject,
            email=_optional_claim(claims, "email", 320),
            display_name=_optional_claim(claims, "name", 200),
            avatar_url=_optional_claim(claims, "picture"),
        )
        db.add(user)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            # Another concurrent login may have created this identity.
            db.rollback()
            user = db.scalar(select(User).where(User.google_sub == subject))
            if user is None:
                raise
        return user

    # Google sub is the identity key; profile attributes may change.
    user.email = _optional_claim(claims, "email", 320)
    user.display_name = _optional_claim(claims, "name", 200)
    user.avatar_url = _optional_claim(claims, "picture")

    db.commit()
    db.refresh(user)
    return user


@router.get("/google/config", response_model=GoogleConfigRead)
def google_config() -> GoogleConfigRead:
    settings = get_settings()
    return GoogleConfigRead(client_id=settings.google_client_id)


@router.post("/google/session", response_model=UserRead)
def google_session(
    payload: GoogleSessionRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    # Login sets cookies, so reject untrusted browser origins.
    validate_allowed_origin(request)

    claims = verify_google_id_token(payload.id_token)
    user = _get_or_create_user(db, claims)

    raw_token, _ = create_session(db, user.id)

    settings = get_settings()
    secure_cookie = settings.app_env.lower() == "production"

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )

    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )

    return user


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    # get_current_user has already checked session, origin and CSRF.
    del current_user

    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    revoke_session(db, raw_token)

    secure_cookie = settings.app_env.lower() == "production"

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=secure_cookie,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        secure=secure_cookie,
        httponly=False,
        samesite="lax",
    )

    return response
