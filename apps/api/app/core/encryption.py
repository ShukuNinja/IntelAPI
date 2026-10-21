from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    """Load and validate the configured encryption key."""
    settings = get_settings()
    configured_key = settings.secret_encryption_key

    if configured_key is None:
        raise RuntimeError(
            "SECRET_ENCRYPTION_KEY must be configured before environment secrets can be processed."
        )

    key = configured_key.get_secret_value().strip()

    if not key:
        raise RuntimeError("SECRET_ENCRYPTION_KEY cannot be empty.")

    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY is invalid. Provide a valid Fernet key.") from exc


def encrypt_secret(value: str) -> bytes:
    """Encrypt a secret value for storage in the database."""
    if not isinstance(value, str):
        raise TypeError("Secret values must be strings.")

    return _get_fernet().encrypt(value.encode("utf-8"))


def decrypt_secret(ciphertext: bytes) -> str:
    """Decrypt a secret value retrieved from the database."""
    if not isinstance(ciphertext, bytes):
        raise TypeError("Ciphertext must be bytes.")

    try:
        plaintext = _get_fernet().decrypt(ciphertext)
    except InvalidToken as exc:
        raise ValueError(
            "The secret cannot be decrypted. The encryption key may "
            "be incorrect, or the stored ciphertext may be invalid."
        ) from exc

    return plaintext.decode("utf-8")
