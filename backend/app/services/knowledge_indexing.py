"""Index knowledge documents with embeddings."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import models
from app.services.embeddings import embed_text


def index_document_text(text: str) -> list[float]:
    return embed_text(text)


def apply_embedding(row: models.KnowledgeDocument, db: Session | None = None) -> None:
    row.embedding = index_document_text(row.text)
    if db is not None and row.id:
        from app.services.vector_search import store_embedding_vector

        store_embedding_vector(db, row.id, row.embedding or [])