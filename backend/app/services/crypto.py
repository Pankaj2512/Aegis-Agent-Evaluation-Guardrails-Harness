"""Fernet encryption for credential secrets at rest, with a key-id prefix.

Encrypted values are stored as ``v1:<fernet-token>``. The ``v1:`` prefix is a
key-id namespace so future key rotation can add ``v2:`` etc. and decrypt legacy
tokens by dispatching on the prefix.

Graceful degradation (mirrors guardrail.py's missing-API-key handling): when
``settings.app_encryption_key`` is unset we log a single loud warning and store
secrets in plaintext rather than crashing dev. ``is_encrypted`` therefore also
recognizes plaintext values as "not encrypted" so the resolve path is safe
either way.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("aegis.crypto")

# Current key-id namespace. Bump (add v2:) when rotating keys.
_KEY_ID = "v1"
_PREFIX = f"{_KEY_ID}:"

_warned_no_key = False


def _fernet():
    """Return a Fernet instance, or None when no key is configured."""
    global _warned_no_key
    key = (settings.app_encryption_key or "").strip()
    if not key:
        if not _warned_no_key:
            logger.warning(
                "app_encryption_key is not configured — credential secrets are stored "
                "in PLAINTEXT. Set app_encryption_key to encrypt secrets at rest.",
                extra={"event": "encryption_disabled"},
            )
            _warned_no_key = True
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        logger.exception(
            "Invalid app_encryption_key (expected a urlsafe base64 32-byte Fernet key); "
            "storing credential secrets in PLAINTEXT.",
            extra={"event": "encryption_key_invalid"},
        )
        return None


def encryption_enabled() -> bool:
    return _fernet() is not None


def is_encrypted(value: object) -> bool:
    """True only for values carrying a known key-id prefix."""
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt_value(value: str) -> str:
    """Encrypt a secret to ``v1:<token>``. Returns plaintext if no key or already encrypted."""
    if not isinstance(value, str) or value == "":
        return value
    if is_encrypted(value):
        return value
    fernet = _fernet()
    if fernet is None:
        return value  # degrade to plaintext (warned once above)
    token = fernet.encrypt(value.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_value(value: str) -> str:
    """Decrypt a ``v1:<token>`` value. Plaintext (no prefix) passes through unchanged."""
    if not is_encrypted(value):
        return value
    fernet = _fernet()
    if fernet is None:
        # Key removed after encryption: cannot recover — return the raw token
        # rather than crash. Caller sees a non-usable secret and can re-enter it.
        logger.error(
            "Cannot decrypt credential secret: app_encryption_key is unset but a "
            "v1-encrypted value exists.",
            extra={"event": "decryption_key_missing"},
        )
        return value
    token = value[len(_PREFIX):]
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        logger.exception(
            "Failed to decrypt credential secret (wrong key?).",
            extra={"event": "decryption_failed"},
        )
        return value
