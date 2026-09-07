"""Named credential resolution for integration nodes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.services.crypto import decrypt_value, encrypt_value

SECRET_KEYS = frozenset(
    {
        "webhook_url",
        "password",
        "api_key",
        "token",
        "connection_url",
        "smtp_password",
    }
)


def mask_credential_config(cred_type: str, config: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in SECRET_KEYS and value:
            masked[key] = "••••••••"
        else:
            masked[key] = value
    return masked


def encrypt_credential_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Encrypt SECRET_KEYS values on the write path (idempotent; degrades to plaintext)."""
    out: dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in SECRET_KEYS and isinstance(value, str) and value:
            out[key] = encrypt_value(value)
        else:
            out[key] = value
    return out


def decrypt_credential_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Decrypt SECRET_KEYS values on the resolve path (plaintext passes through)."""
    out: dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in SECRET_KEYS and isinstance(value, str) and value:
            out[key] = decrypt_value(value)
        else:
            out[key] = value
    return out


def resolve_credential(record: dict[str, Any] | models.Credential | None) -> dict[str, Any]:
    if record is None:
        return {}
    if isinstance(record, models.Credential):
        return decrypt_credential_config(record.config or {})
    return decrypt_credential_config(record.get("config") or {})


def get_user_credential(
    db: Session,
    user_id: UUID,
    credential_id: UUID | None = None,
    name: str | None = None,
) -> models.Credential | None:
    query = db.query(models.Credential).filter(models.Credential.user_id == user_id)
    if credential_id:
        return query.filter(models.Credential.id == credential_id).first()
    if name:
        return query.filter(models.Credential.name == name).first()
    return None