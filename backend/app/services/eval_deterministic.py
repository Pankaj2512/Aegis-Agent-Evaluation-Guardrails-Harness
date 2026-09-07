"""Fast deterministic evaluation strategies (exact, substring, regex, embedding)."""

from __future__ import annotations

import re
from typing import Any

from app.services.embeddings import cosine_similarity_vectors, embed_text

DEFAULT_SIMILARITY_THRESHOLD = 0.75


def _score_dict(
    *,
    eval_type: str,
    passed: bool,
    match_score: float,
    reasoning: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aggregate = round(1.0 + match_score * 4.0, 2)
    payload: dict[str, Any] = {
        "eval_type": eval_type,
        "deterministic": True,
        "passed": passed,
        "match_score": round(match_score, 4),
        "aggregate_score": aggregate,
        "faithfulness": aggregate,
        "helpfulness": aggregate,
        "relevance": aggregate,
        # Deterministic evals do not score toxicity; leave null so averages
        # are not polluted by a synthetic "3" on every failure.
        "toxicity": None,
        "reasoning": reasoning,
    }
    if extra:
        payload.update(extra)
    return payload


def evaluate_exact(content: str, expected: str) -> dict[str, Any]:
    actual = (content or "").strip()
    target = (expected or "").strip()
    passed = actual == target
    return _score_dict(
        eval_type="exact",
        passed=passed,
        match_score=1.0 if passed else 0.0,
        reasoning="Exact match" if passed else f"Expected '{target[:120]}', got '{actual[:120]}'",
        extra={"expected": target},
    )


def evaluate_substring(content: str, expected: str) -> dict[str, Any]:
    actual = content or ""
    needle = (expected or "").strip()
    if not needle:
        return _score_dict(
            eval_type="substring",
            passed=False,
            match_score=0.0,
            reasoning="Substring check requires a non-empty expected value",
        )
    passed = needle.lower() in actual.lower()
    return _score_dict(
        eval_type="substring",
        passed=passed,
        match_score=1.0 if passed else 0.0,
        reasoning=f"Substring '{needle[:80]}' found" if passed else f"Substring '{needle[:80]}' not found",
        extra={"expected_substring": needle},
    )


def evaluate_regex(content: str, pattern: str) -> dict[str, Any]:
    expr = (pattern or "").strip()
    if not expr:
        return _score_dict(
            eval_type="regex",
            passed=False,
            match_score=0.0,
            reasoning="Regex check requires a pattern",
        )
    try:
        matched = re.search(expr, content or "", re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        return _score_dict(
            eval_type="regex",
            passed=False,
            match_score=0.0,
            reasoning=f"Invalid regex pattern: {exc}",
            extra={"pattern": expr},
        )
    passed = matched is not None
    return _score_dict(
        eval_type="regex",
        passed=passed,
        match_score=1.0 if passed else 0.0,
        reasoning=f"Pattern '{expr[:80]}' matched" if passed else f"Pattern '{expr[:80]}' did not match",
        extra={"pattern": expr, "match": matched.group(0)[:120] if matched else None},
    )


def evaluate_embedding_similarity(
    content: str,
    baseline: str,
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    reference = (baseline or "").strip()
    if not reference:
        return _score_dict(
            eval_type="embedding",
            passed=False,
            match_score=0.0,
            reasoning="Embedding similarity requires a baseline answer",
        )
    similarity = cosine_similarity_vectors(embed_text(content or ""), embed_text(reference))
    passed = similarity >= threshold
    return _score_dict(
        eval_type="embedding",
        passed=passed,
        match_score=max(0.0, min(1.0, similarity)),
        reasoning=(
            f"Cosine similarity {similarity:.3f} ≥ threshold {threshold:.3f}"
            if passed
            else f"Cosine similarity {similarity:.3f} < threshold {threshold:.3f}"
        ),
        extra={
            "similarity": round(similarity, 4),
            "threshold": threshold,
            "baseline_preview": reference[:160],
        },
    )


def evaluate_json_schema(content: str) -> dict[str, Any]:
    """Pass when the output parses as JSON (schema-shaped correctness gate)."""
    import json as _json

    try:
        _json.loads(content)
        passed = True
        reason = "Output is valid JSON"
    except Exception as exc:  # noqa: BLE001
        passed = False
        reason = f"Invalid JSON: {exc}"
    score = 5 if passed else 1
    return {
        "eval_type": "json_schema",
        "passed": passed,
        "aggregate_score": float(score),
        "faithfulness": score,
        "helpfulness": score,
        "relevance": score,
        "toxicity": 1,
        "reasoning": reason,
    }


def evaluate_numeric(content: str, expected: str, *, tolerance: float = 0.0) -> dict[str, Any]:
    """Compare the first number in the output against an expected value."""
    import re as _re

    match = _re.search(r"-?\d+(?:\.\d+)?", content or "")
    try:
        expected_value = float(expected)
    except (TypeError, ValueError):
        expected_value = None
    actual = float(match.group(0)) if match else None
    passed = (
        actual is not None
        and expected_value is not None
        and abs(actual - expected_value) <= tolerance
    )
    score = 5 if passed else 1
    return {
        "eval_type": "numeric",
        "passed": passed,
        "aggregate_score": float(score),
        "faithfulness": score,
        "helpfulness": score,
        "relevance": score,
        "toxicity": 1,
        "reasoning": (
            f"actual={actual} expected={expected_value} tolerance={tolerance}"
        ),
    }


def run_deterministic_evaluation(eval_type: str, content: str, meta: dict[str, Any]) -> dict[str, Any]:
    normalized = (eval_type or "exact").lower()
    if normalized == "exact":
        return evaluate_exact(content, str(meta.get("eval_expected") or ""))
    if normalized == "substring":
        return evaluate_substring(content, str(meta.get("eval_expected") or ""))
    if normalized == "regex":
        return evaluate_regex(content, str(meta.get("eval_pattern") or ""))
    if normalized == "json_schema":
        return evaluate_json_schema(content)
    if normalized == "numeric":
        tolerance = meta.get("eval_tolerance")
        return evaluate_numeric(
            content,
            str(meta.get("eval_expected") or ""),
            tolerance=float(tolerance) if tolerance is not None else 0.0,
        )
    if normalized == "embedding":
        threshold = meta.get("eval_similarity_threshold")
        return evaluate_embedding_similarity(
            content,
            str(meta.get("eval_baseline") or ""),
            threshold=float(threshold) if threshold is not None else DEFAULT_SIMILARITY_THRESHOLD,
        )
    raise ValueError(f"Unsupported deterministic eval type: {eval_type}")