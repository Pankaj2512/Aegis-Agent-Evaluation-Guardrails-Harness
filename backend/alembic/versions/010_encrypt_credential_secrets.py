"""Encrypt existing plaintext credential secret values at rest (Fernet).

Idempotent: values already carrying the ``v1:`` key-id prefix are skipped, so
re-running is safe. No-ops (with a warning) when app_encryption_key is unset —
there is nothing to encrypt to. Reversible: downgrade decrypts back to plaintext.

Revision ID: 010_encrypt_credential_secrets
Revises: 009_agentops_tables_backfill
"""

from __future__ import annotations

import json
import logging

import sqlalchemy as sa
from alembic import op

revision = "010_encrypt_credential_secrets"
down_revision = "009_agentops_tables_backfill"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.credential_encryption")

_credentials = sa.table(
    "credentials",
    sa.column("id", sa.Uuid),
    sa.column("config", sa.JSON),
)


def _secret_keys() -> frozenset[str]:
    from app.services.credentials import SECRET_KEYS

    return SECRET_KEYS


def _coerce_config(raw) -> dict | None:
    """config may come back as dict (PG JSONB) or str (SQLite JSON)."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _rewrite(transform, *, require_key: bool) -> None:
    from app.services.crypto import encryption_enabled

    if require_key and not encryption_enabled():
        logger.warning(
            "app_encryption_key is unset — skipping credential secret encryption "
            "migration (secrets remain plaintext until a key is configured)."
        )
        return

    secret_keys = _secret_keys()
    bind = op.get_bind()
    rows = bind.execute(sa.select(_credentials.c.id, _credentials.c.config)).fetchall()
    for row_id, raw_config in rows:
        config = _coerce_config(raw_config)
        if not config:
            continue
        changed = False
        new_config = dict(config)
        for key in secret_keys:
            value = new_config.get(key)
            if isinstance(value, str) and value:
                transformed = transform(value)
                if transformed != value:
                    new_config[key] = transformed
                    changed = True
        if changed:
            bind.execute(
                sa.update(_credentials)
                .where(_credentials.c.id == row_id)
                .values(config=new_config)
            )


def upgrade() -> None:
    from app.services.crypto import encrypt_value

    # encrypt_value is a no-op on already-encrypted values → idempotent.
    _rewrite(encrypt_value, require_key=True)


def downgrade() -> None:
    from app.services.crypto import decrypt_value

    # decrypt_value passes plaintext through unchanged → safe if partially applied.
    _rewrite(decrypt_value, require_key=False)
