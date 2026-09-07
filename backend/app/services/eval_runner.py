"""Parallel and deferred evaluation execution (LLM + deterministic)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.genai import types

from app.config import settings
from app.services.eval import EvalScores, build_eval_instruction, compute_aggregate_score
from app.services.eval_deterministic import run_deterministic_evaluation

logger = logging.getLogger("aegis.eval")

DETERMINISTIC_EVAL_TYPES = frozenset({"exact", "substring", "regex", "embedding", "json_schema", "numeric"})


def _build_eval_prompt(content: str, request_context: str | None) -> str:
    """Judge the content as a response to the original request when we have it —
    otherwise terse-but-correct answers get punished on relevance/helpfulness."""
    body = (content or "")[:8000]
    if request_context:
        return (
            f"Original user request:\n{request_context[:4000]}\n\n"
            f"Evaluate the following content, which is the workflow's response to that request:\n\n{body}"
        )
    return f"Evaluate the following content:\n\n{body}"


def _evaluate_content_sync(
    content: str,
    *,
    preset: str | None,
    criteria: str | None,
    instruction: str | None = None,
    score_weights: dict[str, float] | None = None,
    request_context: str | None = None,
) -> dict[str, Any]:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    system_instruction = instruction or build_eval_instruction(preset, criteria)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=_build_eval_prompt(content, request_context),
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=EvalScores,
        ),
    )
    scores = EvalScores.model_validate_json(response.text or "{}")
    payload = scores.model_dump()
    aggregate = compute_aggregate_score(payload, score_weights)
    if aggregate is not None:
        payload["aggregate_score"] = aggregate
    payload["eval_type"] = "llm"

    # Deferred evals bypass the ADK runner (and its token plugin), so capture
    # usage here; the executor pops this key before persisting scores.
    usage = getattr(response, "usage_metadata", None)
    if usage:
        from app.services.token_tracker import estimate_cost_usd

        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
        total_tokens = int(getattr(usage, "total_token_count", 0) or 0)
        model = getattr(response, "model_version", None) or settings.gemini_model
        usage_row: dict[str, Any] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "thinking_tokens": thinking_tokens,
            "total_tokens": total_tokens,
            "calls": 1,
            "model": str(model),
        }
        cost = estimate_cost_usd(str(model), prompt_tokens, completion_tokens + thinking_tokens)
        if cost is not None:
            usage_row["cost_usd"] = round(cost, 6)
        payload["_token_usage"] = usage_row
    return payload


async def evaluate_node_async(
    content: str,
    meta: dict[str, Any],
    request_context: str | None = None,
) -> dict[str, Any]:
    eval_type = (meta.get("eval_type") or "llm").lower()
    if eval_type in DETERMINISTIC_EVAL_TYPES:
        return await asyncio.to_thread(run_deterministic_evaluation, eval_type, content, meta)

    return await asyncio.to_thread(
        _evaluate_content_sync,
        content,
        preset=meta.get("eval_preset"),
        criteria=meta.get("criteria"),
        instruction=meta.get("eval_instruction"),
        score_weights=meta.get("score_weights"),
        request_context=request_context,
    )


async def evaluate_content_async(
    content: str,
    *,
    preset: str | None = None,
    criteria: str | None = None,
    instruction: str | None = None,
    score_weights: dict[str, float] | None = None,
    request_context: str | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _evaluate_content_sync,
        content,
        preset=preset,
        criteria=criteria,
        instruction=instruction,
        score_weights=score_weights,
        request_context=request_context,
    )


async def run_parallel_evaluations(
    specs: list[tuple[str, dict[str, Any], str]],
    request_context: str | None = None,
) -> list[tuple[str, dict[str, Any] | None, str | None]]:
    """Evaluate multiple nodes concurrently. Returns (node_id, scores, error)."""

    async def _one(node_id: str, meta: dict[str, Any], content: str) -> tuple[str, dict[str, Any] | None, str | None]:
        try:
            scores = await evaluate_node_async(content, meta, request_context)
            return node_id, scores, None
        except Exception as exc:
            logger.warning("Deferred eval failed", extra={"node_id": node_id, "error": str(exc)})
            return node_id, None, str(exc)

    return await asyncio.gather(*[_one(node_id, meta, content) for node_id, meta, content in specs])