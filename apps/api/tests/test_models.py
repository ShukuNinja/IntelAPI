from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import Project, User


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Run each test in a transaction that is rolled back afterward."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_create_user_and_project(db_session: Session) -> None:
    user = User(
        google_sub=f"google-{uuid4()}",
        email="developer@example.com",
        display_name="Test Developer",
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        owner_user_id=user.id,
        name="Test API",
        description="A project for API testing.",
    )
    db_session.add(project)
    db_session.flush()

    stored_user = db_session.get(User, user.id)
    stored_project = db_session.get(Project, project.id)

    assert stored_user is not None
    assert stored_user.google_sub == user.google_sub
    assert stored_project is not None
    assert stored_project.owner_user_id == user.id
    assert stored_project.name == "Test API"
    assert stored_project.deleted_at is None


def test_google_sub_must_be_unique(db_session: Session) -> None:
    google_sub = f"google-{uuid4()}"
    db_session.add(User(google_sub=google_sub))
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(User(google_sub=google_sub))
            db_session.flush()


def test_project_requires_an_existing_owner(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                Project(
                    owner_user_id=uuid4(),
                    name="Orphan Project",
                )
            )
            db_session.flush()


def test_project_can_be_soft_deleted(db_session: Session) -> None:
    user = User(google_sub=f"google-{uuid4()}")
    db_session.add(user)
    db_session.flush()

    project = Project(
        owner_user_id=user.id,
        name="Archived Project",
    )
    db_session.add(project)
    db_session.flush()

    deleted_at = datetime.now(UTC)
    project.deleted_at = deleted_at
    db_session.flush()

    stored_project = db_session.get(Project, project.id)

    assert stored_project is not None
    assert stored_project.deleted_at == deleted_at
    assert db_session.scalar(select(Project.id).where(Project.id == project.id)) == project.id
