"""Text embeddings for vector RAG (Gemini with TF-IDF fallback)."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from app.config import settings
from app.services.knowledge_base import _tokenize

EMBEDDING_DIM = 768
DEFAULT_EMBED_MODEL = "text-embedding-004"


def _hashing_vector(text: str, *, dim: int = EMBEDDING_DIM) -> list[float]:
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def embed_text(text: str) -> list[float]:
    stripped = (text or "").strip()
    if not stripped:
        return [0.0] * EMBEDDING_DIM

    if settings.google_api_key:
        try:
            from google import genai

            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.embed_content(
                model=settings.embedding_model,
                contents=stripped[:8000],
            )
            values = response.embeddings[0].values
            if values:
                return [float(v) for v in values]
        except Exception:
            pass

    return _hashing_vector(stripped)


def cosine_similarity_vectors(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"Embedding dimension mismatch: {len(a)} vs {len(b)}")
    length = len(a)
    dot = sum(a[i] * b[i] for i in range(length))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(length)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(length)))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_by_embedding(
    query: str,
    documents: list[dict[str, Any]],
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    query_vec = embed_text(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc in documents or []:
        embedding = doc.get("embedding")
        if not embedding:
            embedding = embed_text(str(doc.get("text") or ""))
        score = cosine_similarity_vectors(query_vec, embedding)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "text": doc.get("text"),
                    "score": round(score, 4),
                },
            )
        )
    scored.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in scored[: max(1, top_k)]]