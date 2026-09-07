"""Pluggable model-selection seam for evaluation judges and guardrail classifiers.

Today Aegis runs on Google Gemini only (via google-adk). This module centralizes
"which model performs this judge/guardrail call" behind a provider-agnostic
resolver so that, when multi-provider support lands (roadmap P0), a judge-model /
guardrail-model dropdown lights up with zero changes to eval.py / guardrail.py.

Contract: callers pass an optional override (a provider+model dict, a bare model
string, or None) sourced from a preset/policy field; the resolver returns a
concrete model string to hand to the runtime. Unknown/unsupported providers fall
back to the configured Gemini model rather than erroring — never break the
Gemini path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("aegis.model_ref")

# The only provider wired today. Extend this set when multi-provider lands.
_SUPPORTED_PROVIDERS = {"google", "gemini"}


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str


def default_ref() -> ModelRef:
    return ModelRef(provider="google", model=settings.gemini_model)


def available_models() -> list[ModelRef]:
    """Models the UI may offer today (Gemini-only). Grows with multi-provider."""
    return [default_ref()]


def _coerce(override: dict | str | None) -> ModelRef | None:
    if override is None:
        return None
    if isinstance(override, str):
        model = override.strip()
        return ModelRef(provider="google", model=model) if model else None
    if isinstance(override, dict):
        model = str(override.get("model") or "").strip()
        provider = str(override.get("provider") or "google").strip().lower()
        if not model:
            return None
        return ModelRef(provider=provider, model=model)
    return None


def resolve_model(override: dict | str | None = None) -> str:
    """Resolve an override to a concrete model string, defaulting to Gemini.

    Non-Gemini providers are not runnable yet, so we log and fall back rather
    than break execution. Once a provider abstraction exists, replace this
    fallback with real provider dispatch.
    """
    ref = _coerce(override)
    if ref is None:
        return settings.gemini_model
    if ref.provider not in _SUPPORTED_PROVIDERS:
        logger.warning(
            "Model provider %r not yet supported; falling back to Gemini",
            ref.provider,
            extra={"requested_model": ref.model, "provider": ref.provider},
        )
        return settings.gemini_model
    return ref.model or settings.gemini_model


def resolve_judge_model(preset: dict | None = None) -> str:
    """Model for an LLM-as-judge eval. Reads an optional preset['judge_model']."""
    override = preset.get("judge_model") if isinstance(preset, dict) else None
    return resolve_model(override)


def resolve_guardrail_model(rules: dict | None = None) -> str:
    """Model for an LLM/injection/moderation guardrail. Reads rules['guardrail_model']."""
    override = rules.get("guardrail_model") if isinstance(rules, dict) else None
    return resolve_model(override)
