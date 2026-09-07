"""Per-run knowledge document cache."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models


def load_workflow_kb_documents(db: Session, workflow_id: UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(models.KnowledgeDocument)
        .filter(models.KnowledgeDocument.workflow_id == workflow_id)
        .order_by(models.KnowledgeDocument.updated_at.desc())
        .all()
    )
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "text": row.text,
            "embedding": row.embedding,
        }
        for row in rows
    ]