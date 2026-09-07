"""Fast deterministic evaluation strategies (exact, substring, regex, embedding, fuzzy, schema, keywords)."""

from __future__ import annotations

import difflib
import json
import re
from typing import Any

from app.services.embeddings import cosine_similarity_vectors, embed_text

DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_FUZZY_THRESHOLD = 0.80


def extract_json_text(text: str) -> str:
    """Extract JSON string from raw text, unwrapping markdown code fences if present."""
    if not text:
        return ""
    stripped = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return stripped


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


def evaluate_json_schema(
    content: str,
    schema: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Pass when output parses as valid JSON and conforms to optional JSON schema."""
    cleaned = extract_json_text(content)
    try:
        data = json.loads(cleaned)
    except Exception as exc:  # noqa: BLE001
        return _score_dict(
            eval_type="json_schema",
            passed=False,
            match_score=0.0,
            reasoning=f"Invalid JSON: {exc}",
        )

    parsed_schema: dict[str, Any] | None = None
    if isinstance(schema, dict):
        parsed_schema = schema
    elif isinstance(schema, str) and schema.strip():
        try:
            val = json.loads(schema.strip())
            if isinstance(val, dict):
                parsed_schema = val
        except Exception as exc:  # noqa: BLE001
            return _score_dict(
                eval_type="json_schema",
                passed=False,
                match_score=0.0,
                reasoning=f"Invalid JSON Schema definition: {exc}",
                extra={"schema_error": str(exc)},
            )

    if parsed_schema:
        try:
            import jsonschema

            jsonschema.validate(data, parsed_schema)
            return _score_dict(
                eval_type="json_schema",
                passed=True,
                match_score=1.0,
                reasoning="Output conforms to JSON Schema",
                extra={"schema_validated": True},
            )
        except jsonschema.ValidationError as exc:
            return _score_dict(
                eval_type="json_schema",
                passed=False,
                match_score=0.0,
                reasoning=f"Schema validation failed: {exc.message}",
                extra={"schema_validated": True, "error": exc.message, "path": list(exc.path)},
            )
        except jsonschema.SchemaError as exc:
            return _score_dict(
                eval_type="json_schema",
                passed=False,
                match_score=0.0,
                reasoning=f"Invalid schema: {exc.message}",
                extra={"schema_validated": True, "error": exc.message},
            )

    return _score_dict(
        eval_type="json_schema",
        passed=True,
        match_score=1.0,
        reasoning="Output is valid JSON",
        extra={"schema_validated": False},
    )


def evaluate_fuzzy_match(
    content: str,
    expected: str,
    *,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> dict[str, Any]:
    """Score textual similarity using fuzzy string matching (Gestalt pattern matching)."""
    actual = (content or "").strip()
    target = (expected or "").strip()
    if not target:
        return _score_dict(
            eval_type="fuzzy_match",
            passed=False,
            match_score=0.0,
            reasoning="Fuzzy match requires non-empty expected text",
        )
    ratio = difflib.SequenceMatcher(None, actual.lower(), target.lower()).ratio()
    passed = ratio >= threshold
    return _score_dict(
        eval_type="fuzzy_match",
        passed=passed,
        match_score=round(ratio, 4),
        reasoning=(
            f"Fuzzy similarity {ratio:.3f} >= threshold {threshold:.3f}"
            if passed
            else f"Fuzzy similarity {ratio:.3f} < threshold {threshold:.3f}"
        ),
        extra={
            "similarity": round(ratio, 4),
            "threshold": threshold,
            "expected_preview": target[:120],
        },
    )


def _parse_item_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if not isinstance(raw, str):
        return []
    cleaned = raw.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    parts = re.split(r"[\n,]+", cleaned)
    return [p.strip() for p in parts if p.strip()]


def evaluate_contains_all(
    content: str,
    expected: str | list[str],
    *,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Verify that all expected keywords/phrases appear in the content."""
    items = _parse_item_list(expected)
    if not items:
        return _score_dict(
            eval_type="contains_all",
            passed=False,
            match_score=0.0,
            reasoning="Contains-all check requires at least one expected keyword",
        )
    text = content or ""
    haystack = text if case_sensitive else text.lower()
    missing: list[str] = []
    found: list[str] = []
    for item in items:
        needle = item if case_sensitive else item.lower()
        if needle in haystack:
            found.append(item)
        else:
            missing.append(item)

    passed = len(missing) == 0
    match_score = len(found) / len(items)
    reasoning = (
        f"All {len(items)} required keywords present ({', '.join(found[:5])})"
        if passed
        else f"Missing {len(missing)} of {len(items)} keywords: {', '.join(missing[:5])}"
    )
    return _score_dict(
        eval_type="contains_all",
        passed=passed,
        match_score=round(match_score, 4),
        reasoning=reasoning,
        extra={"found": found, "missing": missing, "total_expected": len(items)},
    )


def evaluate_not_contains(
    content: str,
    forbidden: str | list[str],
    *,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Verify that no forbidden keywords/phrases appear in the content."""
    items = _parse_item_list(forbidden)
    if not items:
        return _score_dict(
            eval_type="not_contains",
            passed=True,
            match_score=1.0,
            reasoning="No forbidden terms specified",
        )
    text = content or ""
    haystack = text if case_sensitive else text.lower()
    violations: list[str] = []
    for item in items:
        needle = item if case_sensitive else item.lower()
        if needle in haystack:
            violations.append(item)

    passed = len(violations) == 0
    match_score = 1.0 if passed else 0.0
    reasoning = (
        "No forbidden keywords found"
        if passed
        else f"Forbidden keywords detected ({len(violations)}): {', '.join(violations[:5])}"
    )
    return _score_dict(
        eval_type="not_contains",
        passed=passed,
        match_score=match_score,
        reasoning=reasoning,
        extra={"violations": violations},
    )


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
        schema = meta.get("eval_expected") or meta.get("eval_schema") or meta.get("eval_json_schema")
        return evaluate_json_schema(content, schema=schema)
    if normalized == "fuzzy_match":
        threshold = meta.get("eval_similarity_threshold")
        return evaluate_fuzzy_match(
            content,
            str(meta.get("eval_expected") or ""),
            threshold=float(threshold) if threshold is not None else DEFAULT_FUZZY_THRESHOLD,
        )
    if normalized == "contains_all":
        return evaluate_contains_all(content, meta.get("eval_expected") or "")
    if normalized == "not_contains":
        return evaluate_not_contains(content, meta.get("eval_expected") or "")
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