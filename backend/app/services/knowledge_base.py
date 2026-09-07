"""Keyword and BM25 knowledge retrieval (Lyzr RAG-lite)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def score_document(query: str, document_text: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0
    doc_tokens = set(_tokenize(document_text))
    if not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    return len(overlap) / len(query_tokens)


def _term_freqs(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = float(len(tokens))
    return {term: count / total for term, count in counts.items()}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def score_document_tfidf(query: str, document_text: str, *, corpus_tokens: list[list[str]] | None = None) -> float:
    query_tokens = _tokenize(query)
    doc_tokens = _tokenize(document_text)
    if not query_tokens or not doc_tokens:
        return 0.0

    corpus = corpus_tokens or [doc_tokens]
    doc_count = max(len(corpus), 1)
    df: dict[str, int] = {}
    for tokens in corpus:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    def tfidf_vector(tokens: list[str]) -> dict[str, float]:
        tf = _term_freqs(tokens)
        vec: dict[str, float] = {}
        for term, freq in tf.items():
            idf = math.log((1 + doc_count) / (1 + df.get(term, 0))) + 1
            vec[term] = freq * idf
        return vec

    return _cosine_similarity(tfidf_vector(query_tokens), tfidf_vector(doc_tokens))


def score_document_bm25(query: str, document_text: str, *, avg_dl: float = 120.0, k1: float = 1.5, b: float = 0.75) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    doc_tokens = _tokenize(document_text)
    if not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    freqs = Counter(doc_tokens)
    score = 0.0
    for term in set(query_tokens):
        tf = freqs.get(term, 0)
        if tf == 0:
            continue
        idf = math.log(1 + (1.0 / (tf + 0.5)))
        denom = tf + k1 * (1 - b + b * (doc_len / max(avg_dl, 1.0)))
        score += idf * ((tf * (k1 + 1)) / max(denom, 1e-9))
    return score


def retrieve_documents(
    query: str,
    documents: list[dict[str, Any]],
    *,
    top_k: int = 3,
    method: str = "bm25",
) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    texts = [str(doc.get("text") or "") for doc in documents or []]
    tokenized_corpus = [_tokenize(t) for t in texts]
    avg_dl = sum(len(tokens) for tokens in tokenized_corpus) / max(len(tokenized_corpus), 1)

    if method == "embedding":
        from app.services.embeddings import retrieve_by_embedding

        return retrieve_by_embedding(query, documents, top_k=top_k)

    for doc in documents or []:
        text = str(doc.get("text") or "")
        if not text.strip():
            continue
        if method == "bm25":
            score = score_document_bm25(query, text, avg_dl=avg_dl)
        elif method == "tfidf":
            score = score_document_tfidf(query, text, corpus_tokens=tokenized_corpus)
        else:
            score = score_document(query, text)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "text": text,
                    "score": round(score, 3),
                },
            )
        )
    scored.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in scored[: max(1, top_k)]]