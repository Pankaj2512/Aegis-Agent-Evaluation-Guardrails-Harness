"""Optional Microsoft Presidio integration for entity-based PII detection."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import settings
from app.services.guardrail import GuardrailResult, PII_PATTERNS

logger = logging.getLogger("aegis.guardrail.presidio")

_REDACTED = "[REDACTED]"


@lru_cache(maxsize=1)
def _analyzer_available() -> bool:
    if not settings.presidio_enabled:
        return False
    try:
        from presidio_analyzer import AnalyzerEngine  # noqa: F401

        return True
    except ImportError:
        logger.warning("presidio_enabled but presidio-analyzer is not installed")
        return False


@lru_cache(maxsize=1)
def _get_analyzer():
    from presidio_analyzer import AnalyzerEngine

    return AnalyzerEngine()


def _default_entities(rules: dict[str, Any]) -> list[str]:
    configured = rules.get("presidio_entities")
    if isinstance(configured, list) and configured:
        return [str(entity) for entity in configured]
    return [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "US_SSN",
        "IP_ADDRESS",
        "PERSON",
        "LOCATION",
    ]


def detect_pii_presidio(text: str, rules: dict[str, Any]) -> GuardrailResult:
    if not text.strip():
        return GuardrailResult(passed=True, message="Empty content passed Presidio check")

    if not _analyzer_available():
        for pii_type, regex in PII_PATTERNS.items():
            if regex.search(text):
                return GuardrailResult(
                    passed=False,
                    message=f"PII detected ({pii_type}) via regex fallback",
                    severity="error",
                )
        return GuardrailResult(
            passed=True,
            message="Presidio unavailable — regex fallback found no PII",
            severity="warn",
        )

    try:
        analyzer = _get_analyzer()
        entities = _default_entities(rules)
        results = analyzer.analyze(
            text=text,
            language=rules.get("presidio_language", "en"),
            entities=entities,
        )
        if not results:
            return GuardrailResult(passed=True, message="Presidio found no PII entities")

        labels = sorted({item.entity_type for item in results})
        return GuardrailResult(
            passed=False,
            message=f"Presidio detected PII entities: {', '.join(labels)}",
            severity="error",
        )
    except Exception as exc:
        logger.exception("Presidio analysis failed")
        return GuardrailResult(
            passed=False,
            message=f"Presidio error: {exc}",
            severity="error",
        )


def redact_pii_presidio(text: str, rules: dict[str, Any] | None = None) -> str:
    rules = rules or {}
    if not _analyzer_available():
        redacted = text
        for regex in PII_PATTERNS.values():
            redacted = regex.sub(_REDACTED, redacted)
        return redacted

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        entities = _default_entities(rules)
        findings = analyzer.analyze(
            text=text,
            language=rules.get("presidio_language", "en"),
            entities=entities,
        )
        if not findings:
            return text
        return anonymizer.anonymize(
            text=text,
            analyzer_results=findings,
            operators={"DEFAULT": OperatorConfig("replace", {"new_value": _REDACTED})},
        ).text
    except Exception:
        redacted = text
        for regex in PII_PATTERNS.values():
            redacted = regex.sub(_REDACTED, redacted)
        return redacted