"""RAG-specific evaluation scorers.

The Gemini judge call is not exercised (no key in tests) — the aggregate is a
pure function and the no-key path degrades to a skip marker.
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.rag_metrics import RAG_DIMENSIONS, rag_aggregate, score_rag

client = TestClient(app)


def test_rag_dimensions():
    assert RAG_DIMENSIONS == ("context_precision", "faithfulness", "answer_relevance")


def test_rag_aggregate_is_mean_of_dimensions():
    scores = {"context_precision": 5, "faithfulness": 4, "answer_relevance": 3}
    assert rag_aggregate(scores) == 4.0
    # Missing dimensions are ignored; all-missing → None.
    assert rag_aggregate({}) is None


def test_score_rag_without_key_skips(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = score_rag("What is X?", "X is Y.", "X is defined as Y in the docs.")
    assert result["skipped"] is True
    assert result["rag_aggregate"] is None


def test_rag_preview_endpoint_no_key(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    resp = client.post(
        "/api/eval-presets/rag-preview",
        json={"question": "q", "context": "c", "answer": "a"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped"] is True
