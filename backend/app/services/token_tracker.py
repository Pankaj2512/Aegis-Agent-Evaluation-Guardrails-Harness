"""Per-run token and cost accounting via ADK plugin callbacks.

ADK 2.x's workflow wrapper strips ``usage_metadata`` from the events it
propagates to runner-level consumers, so token counts never reach the
executor's event loop. Model callbacks, however, fire on the raw
``LlmResponse`` before any wrapping — we capture usage there, keyed by the
ADK agent name, and the executor maps agent names back to canvas node ids
after the run completes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

# USD per 1M tokens (input, output). Matched by substring so versioned model
# ids ("gemini-2.5-flash-002") resolve to their family. Extend as needed.
MODEL_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash": (0.30, 2.50),  # estimate — update when pricing is published
    "gemini-3.5-pro": (1.25, 10.00),  # estimate — update when pricing is published
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
}


def estimate_cost_usd(
    model: str | None, prompt_tokens: int, completion_tokens: int
) -> float | None:
    if not model:
        return None
    for family, (input_price, output_price) in MODEL_PRICES_PER_MTOK.items():
        if family in model:
            return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
    return None


def _apply_call_resilience(llm_request: Any) -> None:
    """Set a bounded per-call timeout + backoff retry on the outgoing LlmRequest.

    Uses the genai SDK's native ``http_options`` (timeout in ms) and
    ``retry_options`` (attempts / exponential backoff) so we don't hand-roll a
    retry loop around the ADK invocation. Total worst-case cost is bounded: the
    per-attempt timeout is derived from the per-call budget divided across
    attempts, so retries cannot exceed ``node_llm_timeout_seconds`` and thus
    cannot blow ``run_timeout_seconds`` / budgets.
    """
    from app.config import settings

    try:
        from google.genai import types as _genai_types
    except Exception:  # noqa: BLE001 — genai unavailable (shouldn't happen at runtime)
        return

    config = getattr(llm_request, "config", None)
    if config is None:
        return

    budget_s = max(1, int(getattr(settings, "node_llm_timeout_seconds", 60) or 60))
    max_retries = max(0, int(getattr(settings, "node_llm_max_retries", 2) or 0))
    attempts = max_retries + 1  # genai counts the first try as attempt 1
    initial_delay = float(getattr(settings, "node_llm_retry_initial_delay", 1.0) or 1.0)

    # Divide the per-call budget across attempts so the worst case (all retries)
    # still fits within budget_s. Floor at 5s so a single attempt is not starved.
    per_attempt_s = max(5, int(budget_s / attempts))

    try:
        http_options = getattr(config, "http_options", None)
        if http_options is None:
            http_options = _genai_types.HttpOptions()
        # timeout is milliseconds in the genai SDK.
        http_options.timeout = per_attempt_s * 1000
        if attempts > 1:
            http_options.retry_options = _genai_types.HttpRetryOptions(
                attempts=attempts,
                initial_delay=initial_delay,
                exp_base=2.0,
                max_delay=float(per_attempt_s),
            )
        config.http_options = http_options
    except Exception:  # noqa: BLE001 — never let resilience wiring break a run
        return


def _zero_usage() -> dict[str, int]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "thinking_tokens": 0,
        "total_tokens": 0,
        "calls": 0,
    }


class TokenTrackerPlugin(BasePlugin):
    """Accumulates LLM token usage per ADK agent name for a single run."""

    def __init__(self, capture_calls: bool = True, max_text_chars: int = 20_000) -> None:
        super().__init__(name="aegis_token_tracker")
        self.usage_by_agent: dict[str, dict[str, int]] = defaultdict(_zero_usage)
        self.model_by_agent: dict[str, str] = {}
        self.capture_calls = capture_calls
        self.max_text_chars = max_text_chars
        # Chronological LLM call records for the trace waterfall.
        self.calls: list[dict[str, Any]] = []
        self._pending_starts: dict[tuple[str, str], tuple[float, str | None]] = {}

    @staticmethod
    def _ctx_key(callback_context: Any) -> tuple[str, str]:
        # before/after callbacks receive distinct context objects; key by
        # stable identifiers instead of object identity.
        return (
            str(getattr(callback_context, "invocation_id", "") or ""),
            str(getattr(callback_context, "agent_name", "") or ""),
        )

    @staticmethod
    def _contents_to_text(contents: Any) -> str | None:
        """Flatten genai contents/parts into readable prompt text."""
        if contents is None:
            return None
        if isinstance(contents, str):
            return contents
        chunks: list[str] = []
        items = contents if isinstance(contents, (list, tuple)) else [contents]
        for item in items:
            role = getattr(item, "role", None)
            parts = getattr(item, "parts", None)
            if parts:
                for part in parts:
                    text = getattr(part, "text", None)
                    if text:
                        chunks.append(f"[{role}] {text}" if role else str(text))
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks) if chunks else None

    async def before_model_callback(self, *, callback_context: Any, llm_request: Any) -> None:
        # Inject a bounded per-call timeout + exponential-backoff retry on every
        # model invocation. The whole-run budget stays run_timeout_seconds; this
        # protects individual Gemini calls from hangs/transient 5xx without an
        # explicit retry loop (the genai SDK applies http_options natively).
        _apply_call_resilience(llm_request)

        if not self.capture_calls:
            return None
        import time as _time

        prompt = self._contents_to_text(getattr(llm_request, "contents", None))
        system = getattr(getattr(llm_request, "config", None), "system_instruction", None)
        if system and prompt:
            prompt = f"[system] {system}\n{prompt}"
        elif system:
            prompt = f"[system] {system}"
        self._pending_starts[self._ctx_key(callback_context)] = (
            _time.time(),
            (prompt or "")[: self.max_text_chars] or None,
        )
        return None

    async def after_model_callback(
        self, *, callback_context: Any, llm_response: Any
    ) -> None:
        usage = getattr(llm_response, "usage_metadata", None)
        if not usage:
            return None
        agent = getattr(callback_context, "agent_name", None) or "unknown"
        row = self.usage_by_agent[agent]
        row["prompt_tokens"] += int(getattr(usage, "prompt_token_count", 0) or 0)
        row["completion_tokens"] += int(getattr(usage, "candidates_token_count", 0) or 0)
        row["thinking_tokens"] += int(getattr(usage, "thoughts_token_count", 0) or 0)
        row["total_tokens"] += int(getattr(usage, "total_token_count", 0) or 0)
        row["calls"] += 1
        model = getattr(llm_response, "model_version", None)
        if model:
            self.model_by_agent[agent] = str(model)

        if self.capture_calls:
            import time as _time

            started_at, prompt_text = self._pending_starts.pop(
                self._ctx_key(callback_context), (None, None)
            )
            completion = None
            content = getattr(llm_response, "content", None)
            parts = getattr(content, "parts", None)
            if parts:
                texts = [getattr(pt, "text", None) for pt in parts]
                completion = "\n".join(t for t in texts if t) or None
            prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
            self.calls.append(
                {
                    "agent": agent,
                    "model": str(model) if model else None,
                    "prompt_text": prompt_text,
                    "completion_text": (completion or "")[: self.max_text_chars] or None,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "thinking_tokens": thinking_tokens,
                    "total_tokens": int(getattr(usage, "total_token_count", 0) or 0),
                    "cost_usd": estimate_cost_usd(
                        str(model) if model else None,
                        prompt_tokens,
                        completion_tokens + thinking_tokens,
                    ),
                    "latency_ms": int((_time.time() - started_at) * 1000) if started_at else None,
                    # Absolute wall-clock start so the trace tree can order llm
                    # and tool child-spans chronologically within a node.
                    "started_wall": started_at,
                }
            )
        return None

    def usage_with_cost(self, fallback_model: str | None = None) -> dict[str, dict[str, Any]]:
        """Per-agent usage rows with cost estimates attached."""
        out: dict[str, dict[str, Any]] = {}
        for agent, row in self.usage_by_agent.items():
            model = self.model_by_agent.get(agent) or fallback_model
            # Thinking tokens bill at the output rate.
            output_tokens = row["completion_tokens"] + row.get("thinking_tokens", 0)
            cost = estimate_cost_usd(model, row["prompt_tokens"], output_tokens)
            entry: dict[str, Any] = {**row, "model": model}
            if cost is not None:
                entry["cost_usd"] = round(cost, 6)
            out[agent] = entry
        return out
