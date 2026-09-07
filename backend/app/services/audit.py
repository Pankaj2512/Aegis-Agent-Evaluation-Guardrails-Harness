"""Audit log: who changed what, when. Callers pass an open session; the
entry commits with the caller's transaction."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db import models

logger = logging.getLogger("aegis.audit")


def record_audit(
    db: Session,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    try:
        db.add(
            models.AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                meta=meta,
            )
        )
    except Exception:  # noqa: BLE001 — auditing must never break the operation
        logger.exception("Failed to record audit entry")
