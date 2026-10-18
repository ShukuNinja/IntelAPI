from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import (
    Collection,
    Environment,
    EnvironmentVariable,
    Project,
    SavedRequest,
    User,
)


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


def _create_project(db_session: Session) -> Project:
    user = User(
        google_sub=f"google-{uuid4()}",
        email=f"{uuid4()}@example.com",
        display_name="Workspace Test User",
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        owner_user_id=user.id,
        name=f"Workspace Project {uuid4()}",
    )
    db_session.add(project)
    db_session.flush()

    return project


def test_collection_name_must_be_unique_within_project(
    db_session: Session,
) -> None:
    project = _create_project(db_session)

    db_session.add(Collection(project_id=project.id, name="Requests"))
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                Collection(project_id=project.id, name="Requests")
            )
            db_session.flush()


def test_environment_name_must_be_unique_within_project(
    db_session: Session,
) -> None:
    project = _create_project(db_session)

    db_session.add(Environment(project_id=project.id, name="Development"))
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                Environment(project_id=project.id, name="Development")
            )
            db_session.flush()


def test_environment_variable_requires_exactly_one_value(
    db_session: Session,
) -> None:
    project = _create_project(db_session)
    environment = Environment(
        project_id=project.id,
        name="Development",
    )
    db_session.add(environment)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                EnvironmentVariable(
                    environment_id=environment.id,
                    key="API_URL",
                    value_plain=None,
                    value_ciphertext=None,
                    is_secret=False,
                )
            )
            db_session.flush()


def test_secret_environment_variable_requires_ciphertext(
    db_session: Session,
) -> None:
    project = _create_project(db_session)
    environment = Environment(
        project_id=project.id,
        name="Development",
    )
    db_session.add(environment)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                EnvironmentVariable(
                    environment_id=environment.id,
                    key="API_TOKEN",
                    value_plain="plain-text-secret",
                    value_ciphertext=None,
                    is_secret=True,
                )
            )
            db_session.flush()


def test_saved_request_rejects_invalid_body_type(
    db_session: Session,
) -> None:
    project = _create_project(db_session)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                SavedRequest(
                    project_id=project.id,
                    name="Invalid request",
                    method="GET",
                    url_template="https://example.com",
                    body_type="invalid",
                )
            )
            db_session.flush()


def test_deleting_environment_cascades_to_variables(
    db_session: Session,
) -> None:
    project = _create_project(db_session)
    environment = Environment(
        project_id=project.id,
        name="Development",
    )
    db_session.add(environment)
    db_session.flush()

    variable = EnvironmentVariable(
        environment_id=environment.id,
        key="BASE_URL",
        value_plain="https://example.com",
        is_secret=False,
    )
    db_session.add(variable)
    db_session.flush()

    db_session.execute(
        delete(Environment).where(Environment.id == environment.id)
    )
    db_session.flush()

    remaining_variable = db_session.scalar(
        select(EnvironmentVariable.id).where(
            EnvironmentVariable.id == variable.id
        )
    )
    assert remaining_variable is None


def test_deleting_collection_unlinks_saved_requests(
    db_session: Session,
) -> None:
    project = _create_project(db_session)
    collection = Collection(
        project_id=project.id,
        name="Requests",
    )
    db_session.add(collection)
    db_session.flush()

    saved_request = SavedRequest(
        project_id=project.id,
        collection_id=collection.id,
        name="Get users",
        method="GET",
        url_template="https://example.com/users",
    )
    db_session.add(saved_request)
    db_session.flush()

    db_session.execute(
        delete(Collection).where(Collection.id == collection.id)
    )
    db_session.flush()

    remaining_request_id = db_session.scalar(
        select(SavedRequest.id).where(
            SavedRequest.id == saved_request.id
        )
    )
    remaining_collection_id = db_session.scalar(
        select(SavedRequest.collection_id).where(
            SavedRequest.id == saved_request.id
        )
    )

    assert remaining_request_id == saved_request.id
    assert remaining_collection_id is None