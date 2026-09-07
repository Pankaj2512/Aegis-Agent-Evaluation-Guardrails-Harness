"""Pgvector-backed knowledge retrieval with JSON embedding fallback."""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal
from app.services.embeddings import embed_text, retrieve_by_embedding


def _pgvector_available(db: Session) -> bool:
    if not settings.pgvector_enabled:
        return False
    try:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return False
        row = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
        ).first()
        return row is not None
    except Exception:
        return False


def _validate_embedding(embedding: list[float]) -> list[float]:
    values = [float(v) for v in embedding]
    if any(not math.isfinite(v) for v in values):
        raise ValueError("embedding contains non-finite values")
    return values


def _embedding_literal(embedding: list[float]) -> str:
    values = _validate_embedding(embedding)
    return "[" + ",".join(str(v) for v in values) + "]"


def store_embedding_vector(db: Session, document_id: UUID, embedding: list[float]) -> None:
    if not _pgvector_available(db) or not embedding:
        return
    db.execute(
        text(
            "UPDATE knowledge_documents SET embedding_vector = :vec::vector "
            "WHERE id = :id"
        ),
        {"vec": _embedding_literal(embedding), "id": str(document_id)},
    )


def retrieve_by_pgvector(
    db: Session,
    workflow_id: UUID,
    query: str,
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    if not _pgvector_available(db):
        return []
    query_vec = embed_text(query)
    if not query_vec:
        return []
    rows = db.execute(
        text(
            """
            SELECT id, title, text,
                   1 - (embedding_vector <=> :query_vec::vector) AS score
            FROM knowledge_documents
            WHERE workflow_id = :workflow_id
              AND embedding_vector IS NOT NULL
            ORDER BY embedding_vector <=> :query_vec::vector
            LIMIT :limit
            """
        ),
        {
            "query_vec": _embedding_literal(query_vec),
            "workflow_id": str(workflow_id),
            "limit": max(1, top_k),
        },
    ).mappings().all()
    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "text": row["text"],
            "score": round(float(row["score"] or 0), 4),
        }
        for row in rows
    ]


def retrieve_documents(
    workflow_id: UUID,
    query: str,
    documents: list[dict[str, Any]],
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        if _pgvector_available(db):
            hits = retrieve_by_pgvector(db, workflow_id, query, top_k=top_k)
            if hits:
                return hits
    finally:
        db.close()
    return retrieve_by_embedding(query, documents, top_k=top_k)