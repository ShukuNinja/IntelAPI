
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth.sessions import create_session
from app.core.config import get_settings
from app.db.session import engine, get_db
from app.main import app
from app.models.user import User


@pytest.fixture
def authenticated_client() -> Generator[TestClient, None, None]:
    """Create a test user and session inside a rollback-only transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        user = User(
            google_sub=f"meta-test-{uuid4()}",
            email="meta-test@example.com",
            display_name="Meta Test",
        )
        db.add(user)
        db.flush()

        raw_token, _ = create_session(db, user.id)

        def override_get_db() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            client.cookies.set(
                get_settings().session_cookie_name,
                raw_token,
            )
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()


def test_liveness_does_not_require_database() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_meta_route_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHENTICATED",
            "message": "A valid application session is required.",
        }
    }


def test_meta_route_is_versioned_and_authenticated(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "name": "API Intelligence Platform",
        "version": "0.1.0",
        "status": "scaffold",
    }