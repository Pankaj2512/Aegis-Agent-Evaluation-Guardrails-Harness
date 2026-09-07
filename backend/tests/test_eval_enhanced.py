"""Tests for enhanced deterministic evaluations:
- JSON schema validation with schema enforcement and markdown code fence stripping
- Fuzzy string matching (Levenshtein / Gestalt pattern ratio)
- Contains-all keyword assertions
- Not-contains negative assertions
- Guardrail validate_against_schema with markdown fences
"""

from app.services.eval_deterministic import (
    evaluate_contains_all,
    evaluate_fuzzy_match,
    evaluate_json_schema,
    evaluate_not_contains,
    extract_json_text,
    run_deterministic_evaluation,
)
from app.services.guardrail import validate_against_schema


def test_extract_json_text_unwraps_fences():
    raw_markdown = "```json\n{\n  \"status\": \"success\",\n  \"count\": 10\n}\n```"
    assert extract_json_text(raw_markdown) == '{\n  "status": "success",\n  "count": 10\n}'

    plain_fence = "```\n[1, 2, 3]\n```"
    assert extract_json_text(plain_fence) == "[1, 2, 3]"

    regular_json = '{"a": 1}'
    assert extract_json_text(regular_json) == '{"a": 1}'


def test_evaluate_json_schema_handles_markdown_fence():
    content = "```json\n{\"order_id\": \"ORD-123\", \"total\": 49.99}\n```"
    result = evaluate_json_schema(content)
    assert result["passed"] is True
    assert result["aggregate_score"] == 5.0
    assert result["eval_type"] == "json_schema"


def test_evaluate_json_schema_enforces_schema():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "number"},
        },
        "required": ["name", "score"],
    }
    # Matching
    pass_result = evaluate_json_schema('{"name": "Alice", "score": 95.5}', schema=schema)
    assert pass_result["passed"] is True
    assert pass_result["aggregate_score"] == 5.0
    assert pass_result["schema_validated"] is True

    # Missing required field
    fail_result = evaluate_json_schema('{"name": "Bob"}', schema=schema)
    assert fail_result["passed"] is False
    assert fail_result["aggregate_score"] == 1.0
    assert "score" in fail_result["reasoning"]

    # Wrong type
    type_fail = evaluate_json_schema('{"name": "Charlie", "score": "high"}', schema=schema)
    assert type_fail["passed"] is False
    assert "number" in type_fail["reasoning"]


def test_evaluate_fuzzy_match():
    reference = "The customer requested a refund for order #1024 because the item was damaged."
    similar = "Customer requested refund for order #1024 due to item being damaged."
    different = "The weather today in San Francisco is sunny and 72 degrees."

    pass_result = evaluate_fuzzy_match(similar, reference, threshold=0.7)
    assert pass_result["passed"] is True
    assert pass_result["match_score"] >= 0.7
    assert pass_result["aggregate_score"] > 3.5

    fail_result = evaluate_fuzzy_match(different, reference, threshold=0.7)
    assert fail_result["passed"] is False
    assert fail_result["match_score"] < 0.5


def test_evaluate_contains_all():
    text = "We have confirmed your reservation for table 4 at 7:30 PM. See you tonight!"
    pass_result = evaluate_contains_all(text, "reservation, table, 7:30 PM")
    assert pass_result["passed"] is True
    assert pass_result["match_score"] == 1.0

    fail_result = evaluate_contains_all(text, ["reservation", "parking", "dessert"])
    assert fail_result["passed"] is False
    assert "parking" in fail_result["missing"]
    assert "dessert" in fail_result["missing"]
    assert len(fail_result["found"]) == 1


def test_evaluate_not_contains():
    clean_text = "Here is the summary of your quarterly earnings."
    pass_result = evaluate_not_contains(clean_text, "As an AI, I cannot, competitor_corp")
    assert pass_result["passed"] is True
    assert pass_result["match_score"] == 1.0

    flagged_text = "As an AI language model, I cannot provide financial advice."
    fail_result = evaluate_not_contains(flagged_text, ["As an AI", "competitor_corp"])
    assert fail_result["passed"] is False
    assert "As an AI" in fail_result["violations"]


def test_run_deterministic_evaluation_dispatch():
    # Fuzzy match via meta
    res = run_deterministic_evaluation(
        "fuzzy_match",
        "Hello beautiful world",
        {"eval_expected": "Hello world", "eval_similarity_threshold": 0.6},
    )
    assert res["passed"] is True

    # Contains all via meta
    res = run_deterministic_evaluation(
        "contains_all",
        "Error: Invalid authorization token provided",
        {"eval_expected": "Error, authorization token"},
    )
    assert res["passed"] is True

    # Not contains via meta
    res = run_deterministic_evaluation(
        "not_contains",
        "Safe and clean response",
        {"eval_expected": "leak, password, secret"},
    )
    assert res["passed"] is True


def test_guardrail_validate_against_schema_markdown_support():
    schema = {
        "type": "object",
        "properties": {"action": {"type": "string"}},
        "required": ["action"],
    }
    markdown_content = "```json\n{\"action\": \"reboot\"}\n```"
    ok, err = validate_against_schema(markdown_content, schema)
    assert ok is True
    assert err == ""
