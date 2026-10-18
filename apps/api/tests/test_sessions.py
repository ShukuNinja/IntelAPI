from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import sessions
from app.db.session import engine
from app.models import User
from app.models.user_session import UserSession


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Run each test in a transaction that is rolled back afterward."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
    bind=connection,
    expire_on_commit=False,
    join_transaction_mode="create_savepoint",
)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a user for session tests."""
    user = User(
        google_sub=f"google-{uuid4()}",
        email="session-test@example.com",
        display_name="Session Test",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_create_session_stores_only_token_hash(
    db_session: Session,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sessions,
        "get_settings",
        lambda: SimpleNamespace(session_ttl_seconds=3600),
    )

    raw_token, record = sessions.create_session(db_session, test_user.id)

    assert raw_token
    assert len(raw_token) >= 32
    assert record.user_id == test_user.id
    assert record.token_hash == sessions._hash_token(raw_token)
    assert record.token_hash != raw_token.encode("utf-8")
    assert record.expires_at > datetime.now(UTC)

    stored = db_session.scalar(
        select(UserSession).where(UserSession.id == record.id)
    )
    assert stored is not None
    assert stored.token_hash == sessions._hash_token(raw_token)


def test_active_session_resolves_to_user(
    db_session: Session,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sessions,
        "get_settings",
        lambda: SimpleNamespace(session_ttl_seconds=3600),
    )
    raw_token, _ = sessions.create_session(db_session, test_user.id)

    resolved_user = sessions.get_user_for_session(db_session, raw_token)

    assert resolved_user is not None
    assert resolved_user.id == test_user.id


@pytest.mark.parametrize("raw_token", [None, ""])
def test_missing_token_does_not_resolve_user(
    db_session: Session,
    raw_token: str | None,
) -> None:
    assert sessions.get_user_for_session(db_session, raw_token) is None


def test_unknown_token_does_not_resolve_user(db_session: Session) -> None:
    assert (
        sessions.get_user_for_session(db_session, "unknown-session-token")
        is None
    )


def test_expired_session_does_not_resolve_user(
    db_session: Session,
    test_user: User,
) -> None:
    raw_token = "expired-test-token"
    record = UserSession(
        user_id=test_user.id,
        token_hash=sessions._hash_token(raw_token),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(record)
    db_session.flush()

    assert sessions.get_user_for_session(db_session, raw_token) is None


def test_revoked_session_does_not_resolve_user(
    db_session: Session,
    test_user: User,
) -> None:
    raw_token = "revoked-test-token"
    record = UserSession(
        user_id=test_user.id,
        token_hash=sessions._hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=datetime.now(UTC),
    )
    db_session.add(record)
    db_session.flush()

    assert sessions.get_user_for_session(db_session, raw_token) is None


def test_revoke_session_marks_record_revoked(
    db_session: Session,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sessions,
        "get_settings",
        lambda: SimpleNamespace(session_ttl_seconds=3600),
    )
    raw_token, record = sessions.create_session(db_session, test_user.id)

    assert sessions.revoke_session(db_session, raw_token) is True

    db_session.refresh(record)
    assert record.revoked_at is not None
    assert sessions.get_user_for_session(db_session, raw_token) is None


def test_revoke_unknown_or_missing_token_returns_false(
    db_session: Session,
) -> None:
    assert sessions.revoke_session(db_session, None) is False
    assert sessions.revoke_session(db_session, "unknown-token") is False


def test_revoke_session_is_idempotent(
    db_session: Session,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sessions,
        "get_settings",
        lambda: SimpleNamespace(session_ttl_seconds=3600),
    )
    raw_token, _ = sessions.create_session(db_session, test_user.id)

    assert sessions.revoke_session(db_session, raw_token) is True
    assert sessions.revoke_session(db_session, raw_token) is False