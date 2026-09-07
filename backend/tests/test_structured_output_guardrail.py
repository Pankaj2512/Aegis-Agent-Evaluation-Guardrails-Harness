"""Structured-output guardrail: JSON-schema validation + bounded re-ask.

The re-ask (LLM repair) loop is not exercised (no key in tests) — the pure
schema validation and the no-key failure path are. Schema validation is
factored out so it's directly testable.
"""

from app.config import settings
from app.services.guardrail import (
    validate_against_schema,
    validate_guardrail_content,
    validate_structured_output,
)

SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}


def test_valid_json_matches_schema():
    ok, err = validate_against_schema('{"name": "Ada", "age": 36}', SCHEMA)
    assert ok is True
    assert err == ""


def test_non_json_fails():
    ok, err = validate_against_schema("not json at all", SCHEMA)
    assert ok is False
    assert "not valid JSON" in err


def test_json_missing_required_field_fails():
    ok, err = validate_against_schema('{"name": "Ada"}', SCHEMA)
    assert ok is False
    assert "age" in err


def test_validator_passes_matching_output():
    result = validate_structured_output('{"name": "Ada", "age": 36}', {"json_schema": SCHEMA})
    assert result.passed is True
    assert "matches" in result.message


def test_no_schema_configured_passes_with_warning():
    result = validate_structured_output('{"anything": true}', {})
    assert result.passed is True
    assert result.severity == "warn"


def test_invalid_output_without_key_fails(monkeypatch):
    # No API key → the re-ask loop can't run, so an invalid output must fail.
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = validate_structured_output('{"name": "Ada"}', {"json_schema": SCHEMA, "reask": True})
    assert result.passed is False
    assert result.severity == "error"


def test_routing_via_guardrail_content(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = validate_guardrail_content(
        '{"name": "Ada", "age": 36}',
        {"guardrail_type": "json_schema", "json_schema": SCHEMA},
    )
    assert result.passed is True
