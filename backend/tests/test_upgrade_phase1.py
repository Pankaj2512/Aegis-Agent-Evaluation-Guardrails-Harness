from unittest.mock import AsyncMock, patch

import pytest

from app.services.compiler import compile_workflow
from app.services.eval_runner import run_parallel_evaluations
from app.services.guardrail import apply_fail_behavior, redact_pii, validate_content
from tests.conftest import valid_graph


def test_compile_parallel_eval_metadata():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Eval",
                    "nodeType": "evaluation",
                    "evalExecutionMode": "parallel",
                    "evalThreshold": 3.5,
                },
            },
        ],
    )
    _workflow, metadata, _ = compile_workflow(graph)
    assert metadata["eval1"]["eval_deferred"] is True
    assert metadata["eval1"]["eval_execution_mode"] == "parallel"


def test_compile_inline_eval_not_deferred():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Eval",
                    "nodeType": "evaluation",
                    "evalExecutionMode": "inline",
                },
            },
        ],
    )
    _workflow, metadata, _ = compile_workflow(graph)
    assert metadata["eval1"]["eval_deferred"] is False


@pytest.mark.asyncio
async def test_run_parallel_evaluations_executes_concurrently():
    with patch("app.services.eval_runner.evaluate_node_async", new_callable=AsyncMock) as mock_eval:
        mock_eval.side_effect = [
            {"faithfulness": 5, "helpfulness": 4, "relevance": 4, "toxicity": 1, "aggregate_score": 4.5},
            {"faithfulness": 3, "helpfulness": 3, "relevance": 3, "toxicity": 2, "aggregate_score": 3.1},
        ]
        specs = [
            ("eval1", {"eval_preset": "rag_quality"}, "answer one"),
            ("eval2", {"criteria": "tone"}, "answer two"),
        ]
        results = await run_parallel_evaluations(specs)
        assert len(results) == 2
        assert results[0][1]["aggregate_score"] == 4.5
        assert results[1][1]["aggregate_score"] == 3.1
        assert mock_eval.await_count == 2


def test_redact_pii_masks_email_and_phone():
    text = "Contact ada@example.com or call 555-123-4567"
    redacted = redact_pii(text)
    assert "ada@example.com" not in redacted
    assert "555-123-4567" not in redacted
    assert "[REDACTED]" in redacted


def test_guardrail_mask_fail_behavior_continues_with_redacted_output():
    failed = validate_content("reach me at user@example.com", {"detect_pii": True})
    assert failed.passed is False
    handled = apply_fail_behavior(
        failed,
        "mask",
        "g1",
        content="reach me at user@example.com",
    )
    assert handled.passed is True
    assert handled.output_override is not None
    assert "user@example.com" not in handled.output_override


def test_guardrail_fallback_fail_behavior_uses_safe_string():
    failed = validate_content("badword", {"blocked_keywords": ["badword"]})
    handled = apply_fail_behavior(
        failed,
        "fallback",
        "g1",
        rules={"fallback_value": "Safe default reply"},
    )
    assert handled.passed is True
    assert handled.output_override == "Safe default reply"