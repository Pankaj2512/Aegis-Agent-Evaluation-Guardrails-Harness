import pytest

from app.services.guardrail import (
    GuardrailBlockedError,
    apply_fail_behavior,
    validate_content,
)


def test_validate_pii_email():
    result = validate_content("Contact me at user@example.com", {"detect_pii": True})
    assert not result.passed
    assert "email" in result.message.lower()


def test_validate_max_length():
    result = validate_content("hello world", {"max_length": 5})
    assert not result.passed


def test_warn_mode_continues():
    result = validate_content("bad spam content", {"blocked_keywords": ["spam"]})
    warned = apply_fail_behavior(result, "warn", "n1")
    assert warned.passed
    assert warned.severity == "warn"


def test_block_mode_raises():
    result = validate_content("bad spam", {"blocked_keywords": ["spam"]})
    with pytest.raises(GuardrailBlockedError):
        apply_fail_behavior(result, "block", "n1")


def test_validate_blocked_pattern_list():
    result = validate_content("api_key=abc", {"blocked_patterns": [r"api_key\s*="]})
    assert not result.passed