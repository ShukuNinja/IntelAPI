from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import secret_storage
from app.core.config import Settings
from app.db.base import Base
from app.models import Environment, Project, User
from app.modules.client.router import _environment_response


def _settings_with_key(key: str) -> Settings:
    return Settings(environment_encryption_key=key)


def test_environment_secret_ciphertext_can_be_decrypted_without_echoing_plaintext(
    monkeypatch,
) -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(secret_storage, "get_settings", lambda: _settings_with_key(key))
    secret = "private-access-token"

    encrypted = secret_storage.encrypt_environment_values({"token": secret})

    assert encrypted["token"] != secret
    assert secret not in encrypted["token"]
    assert secret_storage.decrypt_environment_values(encrypted) == {"token": secret}


def test_environment_response_migrates_legacy_values_to_write_only_secrets(
    monkeypatch,
) -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(secret_storage, "get_settings", lambda: _settings_with_key(key))
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = User(google_sub="intelapi-local-single-user", display_name="Local user")
            db.add(user)
            db.flush()
            project = Project(owner_user_id=user.id, name="Secret migration")
            db.add(project)
            db.flush()
            environment = Environment(
                project_id=project.id,
                name="Legacy environment",
                variables={"token": "private-access-token"},
                secret_variables={},
                secrets_migrated=False,
            )
            db.add(environment)
            db.commit()

            response = _environment_response(environment, db)

            assert response["variables"] == {}
            assert response["secrets"] == {"token": {"has_value": True}}
            assert "private-access-token" not in str(response)
            assert "private-access-token" not in environment.secret_variables["token"]
            assert secret_storage.decrypt_environment_values(environment.secret_variables) == {
                "token": "private-access-token"
            }
            assert environment.secrets_migrated is True
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
