"""Trust-layer Phase 3: moderation/toxicity guardrail rail.

Covers the pure score→verdict mapping (per-category thresholds), the guardrail
routing, and the no-API-key skip path. The Gemini call itself is not exercised
(no key in tests) — the scoring logic is factored out to be testable directly.
"""

from app.config import settings
from app.services.guardrail import (
    MODERATION_CATEGORIES,
    _evaluate_moderation_scores,
    validate_guardrail_content,
)


def test_categories_are_the_expected_five():
    assert MODERATION_CATEGORIES == ("toxicity", "hate", "violence", "self_harm", "sexual")


def test_below_threshold_passes():
    scores = {"toxicity": 0.2, "hate": 0.1, "violence": 0.0, "self_harm": 0.0, "sexual": 0.0}
    result = _evaluate_moderation_scores(scores, {})
    assert result.passed is True
    assert "passed moderation" in result.message


def test_above_default_threshold_flags():
    scores = {"toxicity": 0.9, "hate": 0.0, "violence": 0.0, "self_harm": 0.0, "sexual": 0.0}
    result = _evaluate_moderation_scores(scores, {})
    assert result.passed is False
    assert result.severity == "error"
    assert "toxicity" in result.message


def test_custom_single_threshold():
    scores = {"toxicity": 0.4, "hate": 0.0, "violence": 0.0, "self_harm": 0.0, "sexual": 0.0}
    # Default 0.5 -> passes; a stricter 0.3 -> flags.
    assert _evaluate_moderation_scores(scores, {}).passed is True
    assert _evaluate_moderation_scores(scores, {"moderation_threshold": 0.3}).passed is False


def test_per_category_thresholds_override_default():
    scores = {"toxicity": 0.35, "hate": 0.0, "violence": 0.0, "self_harm": 0.0, "sexual": 0.0}
    rules = {"moderation_threshold": 0.9, "moderation_thresholds": {"toxicity": 0.3}}
    result = _evaluate_moderation_scores(scores, rules)
    assert result.passed is False
    assert "toxicity" in result.message


def test_malformed_scores_do_not_crash():
    scores = {"toxicity": "oops", "hate": None}
    result = _evaluate_moderation_scores(scores, {"moderation_threshold": "bad"})
    assert result.passed is True  # unparseable → treated as 0, default threshold


def test_routing_and_no_key_skip(monkeypatch):
    # validate_guardrail_content dispatches guardrail_type "moderation" to the
    # moderation rail. Force the no-key path (deterministic, avoids a live LLM
    # call) — it must degrade to a warn-level pass rather than error.
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = validate_guardrail_content("some content", {"guardrail_type": "moderation"})
    assert result.passed is True
    assert result.severity == "warn"
    assert "GOOGLE_API_KEY" in result.message
