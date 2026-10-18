import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.models.user_session import UserSession


def _hash_token(raw_token: str) -> bytes:
    """Hash a session token before storing or querying it."""
    return hashlib.sha256(raw_token.encode("utf-8")).digest()


def create_session(
    db: Session,
    user_id: UUID,
) -> tuple[str, UserSession]:
    """Create a session and return its raw token and database record."""
    settings = get_settings()

    # Generate a cryptographically secure, unpredictable token.
    raw_token = secrets.token_urlsafe(32)

    now = datetime.now(UTC)

    session_record = UserSession(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
    )

    db.add(session_record)
    db.commit()
    db.refresh(session_record)

    # The raw token is returned for the HTTP-only cookie.
    # Only its SHA-256 hash is stored in the database.
    return raw_token, session_record


def get_user_for_session(
    db: Session,
    raw_token: str | None,
) -> User | None:
    """Return the user only if the session is valid and active."""
    if not raw_token:
        return None

    now = datetime.now(UTC)
    token_hash = _hash_token(raw_token)

    statement = (
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )

    return db.scalar(statement)


def revoke_session(
    db: Session,
    raw_token: str | None,
) -> bool:
    """Revoke an active session. Return whether one was found."""
    if not raw_token:
        return False

    token_hash = _hash_token(raw_token)

    statement = select(UserSession).where(
        UserSession.token_hash == token_hash,
        UserSession.revoked_at.is_(None),
    )

    session_record = db.scalar(statement)

    if session_record is None:
        return False

    session_record.revoked_at = datetime.now(UTC)
    db.commit()

    return True
