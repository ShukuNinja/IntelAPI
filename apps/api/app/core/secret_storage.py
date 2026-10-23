from typing import Any

from app.core.config import get_settings


class SecretStorageError(ValueError):
    """Secret encryption is unavailable or stored ciphertext cannot be opened."""


def _fernet() -> Any:
    key = get_settings().environment_encryption_key
    if key is None or not key.get_secret_value().strip():
        raise SecretStorageError(
            "Environment secret storage is not configured. Set ENVIRONMENT_ENCRYPTION_KEY."
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.get_secret_value().encode("ascii"))
    except ImportError as exc:
        raise SecretStorageError(
            "Environment secret storage is unavailable. Install the API dependencies."
        ) from exc
    except (ValueError, UnicodeEncodeError) as exc:
        raise SecretStorageError("ENVIRONMENT_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_environment_values(values: dict[str, str]) -> dict[str, str]:
    if not values:
        return {}
    cipher = _fernet()
    return {
        name: cipher.encrypt(value.encode("utf-8")).decode("ascii")
        for name, value in values.items()
    }


def decrypt_environment_values(values: dict[str, str]) -> dict[str, str]:
    if not values:
        return {}
    cipher = _fernet()
    try:
        from cryptography.fernet import InvalidToken

        return {
            name: cipher.decrypt(value.encode("ascii")).decode("utf-8")
            for name, value in values.items()
        }
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise SecretStorageError(
            "An environment secret could not be decrypted. Check ENVIRONMENT_ENCRYPTION_KEY."
        ) from exc
