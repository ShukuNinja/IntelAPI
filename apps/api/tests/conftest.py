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
            google_sub=f"test-user-{uuid4()}",
            email=f"{uuid4()}@example.com",
            display_name="Test User",
        )
        db.add(user)
        db.flush()

        raw_token, _ = create_session(db, user.id)

        def override_get_db() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(
            app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        ) as client:
            client.cookies.set(
                get_settings().session_cookie_name,
                raw_token,
            )

            # Match the CSRF cookie to the request header.
            csrf_token = "test-csrf-token"
            client.cookies.set("csrf_token", csrf_token)
            client.headers["X-CSRF-Token"] = csrf_token

            yield client

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def second_authenticated_client() -> Generator[TestClient, None, None]:
    """Create a second authenticated user in a rollback-only transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        user = User(
            google_sub=f"test-user-{uuid4()}",
            email=f"{uuid4()}@example.com",
            display_name="Second Test User",
        )
        db.add(user)
        db.flush()

        raw_token, _ = create_session(db, user.id)

        def override_get_db() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(
            app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        ) as client:
            client.cookies.set(
                get_settings().session_cookie_name,
                raw_token,
            )

            csrf_token = "second-test-csrf-token"
            client.cookies.set("csrf_token", csrf_token)
            client.headers["X-CSRF-Token"] = csrf_token

            yield client

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def two_authenticated_clients() -> Generator[tuple[TestClient, TestClient], None, None]:
    """Create two authenticated users sharing one rollback-only DB transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        clients: list[TestClient] = []

        for label in ("First", "Second"):
            user = User(
                google_sub=f"test-user-{uuid4()}",
                email=f"{uuid4()}@example.com",
                display_name=f"{label} Test User",
            )
            db.add(user)
            db.flush()

            raw_token, _ = create_session(db, user.id)

            client = TestClient(
                app,
                base_url="http://localhost:8000",
                headers={"Origin": "http://localhost:8000"},
            )
            client.cookies.set(
                get_settings().session_cookie_name,
                raw_token,
            )
            csrf_token = f"test-csrf-{uuid4()}"
            client.cookies.set("csrf_token", csrf_token)
            client.headers["X-CSRF-Token"] = csrf_token
            clients.append(client)

        def override_get_db() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            yield clients[0], clients[1]
        finally:
            for client in clients:
                client.close()

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
