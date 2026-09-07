"""Guards for the pluggable judge/guardrail model seam (Trust-layer P0).

The seam must never break today's Gemini-only path: with no override, and for
any not-yet-supported provider, it resolves to the configured Gemini model.
"""

from app.config import settings
from app.services import model_ref


def test_default_resolves_to_gemini():
    assert model_ref.resolve_model() == settings.gemini_model
    assert model_ref.resolve_judge_model(None) == settings.gemini_model
    assert model_ref.resolve_guardrail_model(None) == settings.gemini_model
    assert model_ref.resolve_guardrail_model({}) == settings.gemini_model


def test_gemini_override_string_and_dict():
    assert model_ref.resolve_model("gemini-2.5-pro") == "gemini-2.5-pro"
    assert (
        model_ref.resolve_model({"provider": "google", "model": "gemini-2.5-pro"})
        == "gemini-2.5-pro"
    )
    assert (
        model_ref.resolve_judge_model({"judge_model": "gemini-2.5-pro"})
        == "gemini-2.5-pro"
    )
    assert (
        model_ref.resolve_guardrail_model({"guardrail_model": "gemini-2.5-pro"})
        == "gemini-2.5-pro"
    )


def test_unsupported_provider_falls_back_to_gemini_not_error():
    # Until a provider abstraction exists, unknown providers must degrade to
    # Gemini rather than break execution.
    assert (
        model_ref.resolve_model({"provider": "openai", "model": "gpt-5"})
        == settings.gemini_model
    )
    assert (
        model_ref.resolve_guardrail_model({"guardrail_model": {"provider": "anthropic", "model": "claude"}})
        == settings.gemini_model
    )


def test_available_models_is_gemini_only_today():
    models = model_ref.available_models()
    assert len(models) == 1
    assert models[0].provider == "google"
    assert models[0].model == settings.gemini_model
