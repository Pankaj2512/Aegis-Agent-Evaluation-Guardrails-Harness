"""RAG-specific evaluation scorers.

The Gemini judge call is not exercised (no key in tests) — the aggregate is a
pure function and the no-key path degrades to a skip marker.
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.rag_metrics import (
    RAG_DIMENSIONS,
    assess_hallucination_risk,
    compute_grounding_ratio,
    rag_aggregate,
    score_rag,
)

client = TestClient(app)


def test_rag_dimensions():
    assert RAG_DIMENSIONS == ("context_precision", "faithfulness", "answer_relevance")


def test_rag_aggregate_is_mean_of_dimensions():
    scores = {"context_precision": 5, "faithfulness": 4, "answer_relevance": 3}
    assert rag_aggregate(scores) == 4.0
    # Missing dimensions are ignored; all-missing → None.
    assert rag_aggregate({}) is None


def test_compute_grounding_ratio_cases():
    # Full overlap
    context = "The quick brown fox jumps over the lazy dog."
    answer = "quick brown fox lazy dog"
    assert compute_grounding_ratio(answer, context) == 1.0

    # Zero overlap
    answer_zero = "completely unrelated spaceship galaxy"
    assert compute_grounding_ratio(answer_zero, context) == 0.0

    # Partial overlap (2 of 4 tokens)
    answer_partial = "quick brown spaceship galaxy"
    assert compute_grounding_ratio(answer_partial, context) == 0.5

    # Boundary: empty strings
    assert compute_grounding_ratio("", context) == 0.0
    assert compute_grounding_ratio(answer, "") == 0.0
    assert compute_grounding_ratio("   ", "   ") == 0.0


def test_assess_hallucination_risk_matrix():
    # Strong alignment (low risk, high confidence)
    low_risk = assess_hallucination_risk(faithfulness=5.0, grounding_ratio=0.9)
    assert low_risk["risk_level"] == "LOW"
    assert low_risk["confidence"] == "HIGH"
    assert "strong_lexical_grounding" in low_risk["flags"]

    # Low alignment (high risk, high confidence)
    high_risk = assess_hallucination_risk(faithfulness=1.5, grounding_ratio=0.2)
    assert high_risk["risk_level"] == "HIGH"
    assert high_risk["confidence"] == "HIGH"
    assert "unsupported_claims_likely" in high_risk["flags"]
    assert "low_semantic_faithfulness" in high_risk["flags"]

    # Only grounding available (no LLM judge key)
    grounded_offline = assess_hallucination_risk(faithfulness=None, grounding_ratio=0.85)
    assert grounded_offline["risk_level"] == "LOW"
    assert grounded_offline["confidence"] == "MEDIUM"

    ungrounded_offline = assess_hallucination_risk(faithfulness=None, grounding_ratio=0.1)
    assert ungrounded_offline["risk_level"] == "HIGH"
    assert "unsupported_claims_likely" in ungrounded_offline["flags"]

    # Insufficient data
    unknown = assess_hallucination_risk(faithfulness=None, grounding_ratio=None)
    assert unknown["risk_level"] == "UNKNOWN"
    assert unknown["confidence"] == "LOW"
    assert "insufficient_data" in unknown["flags"]


def test_score_rag_without_key_skips_with_grounding_and_risk(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = score_rag("What is X?", "X is Y.", "X is defined as Y in the docs.")
    assert result["skipped"] is True
    assert result["rag_aggregate"] is None
    assert "grounding_ratio" in result
    assert result["grounding_ratio"] > 0.5
    assert "hallucination_risk" in result
    assert result["hallucination_risk"]["risk_level"] == "LOW"


def test_rag_preview_endpoint_no_key(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    resp = client.post(
        "/api/eval-presets/rag-preview",
        json={"question": "q", "context": "c", "answer": "a"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped"] is True
    assert "grounding_ratio" in resp.json()
    assert "hallucination_risk" in resp.json()

