"""Workflow-level guardrail policy enforced through ADK plugin callbacks.

A per-node guardrail only guards where it sits in the graph. A workflow-level
policy applies one rail to *every* agent's model call — its input (via
``before_model_callback``) and/or its output (via ``after_model_callback``) —
without adding nodes. ADK's callback contract makes this clean:

- ``before_model_callback`` returning a non-``None`` ``LlmResponse`` short-
  circuits the model call (used to block unsafe input).
- ``after_model_callback`` returning a non-``None`` ``LlmResponse`` replaces the
  model's response (used to mask or block unsafe output).

Enforcement is a *soft* block — the offending call is replaced with a safe
message and the run completes — so behaviour is deterministic and never leaves
a half-finished run. Every decision is recorded as a guardrail event that the
executor folds into the run metrics, so workflow-level verdicts land on the
same Trust surface (violation drill-down, Safety tile) as node-level ones.
"""

from __future__ import annotations

import json
from typing import Any

from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from app.services.guardrail import (
    apply_fail_behavior,
    validate_guardrail_content,
)

_OVERRIDE_BEHAVIORS = frozenset({"mask", "rewrite", "fallback"})


def _contents_to_text(contents: Any) -> str | None:
    """Flatten genai contents/parts into readable text (mirrors token_tracker)."""
    if contents is None:
        return None
    if isinstance(contents, str):
        return contents
    chunks: list[str] = []
    items = contents if isinstance(contents, (list, tuple)) else [contents]
    for item in items:
        parts = getattr(item, "parts", None)
        if parts:
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    chunks.append(str(text))
        elif isinstance(item, str):
            chunks.append(item)
    return "\n".join(chunks) if chunks else None


def _response_text(llm_response: Any) -> str | None:
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None)
    if not parts:
        return None
    texts = [getattr(pt, "text", None) for pt in parts]
    return "\n".join(t for t in texts if t) or None


def _expects_json(llm_request: Any) -> bool:
    """True when the agent asked the model for JSON (structured output_schema).

    Aegis compiles most agents with ``output_schema=str``, so ADK sets a JSON
    response format and json-loads the model output. A replacement must match
    that serialization or downstream schema validation fails.
    """
    cfg = getattr(llm_request, "config", None)
    if cfg is None:
        return False
    mime = getattr(cfg, "response_mime_type", None)
    if mime and "json" in str(mime).lower():
        return True
    return getattr(cfg, "response_schema", None) is not None


def _decode_str_response(text: str) -> tuple[str, bool]:
    """Return ``(content_to_validate, was_json_string)``.

    A ``str`` output_schema arrives JSON-encoded (``"hello"``). Validate the
    decoded content, and remember it was JSON so the replacement re-encodes.
    Non-string JSON (objects/lists) is left untouched — we don't rewrite
    structured payloads.
    """
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return (text, False)
    if isinstance(value, str):
        return (value, True)
    return (text, False)


def _text_response(text: str, *, as_json: bool = False) -> LlmResponse:
    payload = json.dumps(text) if as_json else text
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=payload)]))


class GuardrailPolicyPlugin(BasePlugin):
    """Applies a single guardrail policy to every agent's model input/output.

    ``mode`` selects which side(s) to guard: ``input`` (before the model),
    ``output`` (after), or ``both``.
    """

    def __init__(
        self,
        rules: dict[str, Any],
        *,
        mode: str = "both",
        policy_name: str = "Workflow policy",
    ) -> None:
        super().__init__(name="aegis_guardrail_policy")
        self.rules = dict(rules or {})
        self.mode = mode if mode in ("input", "output", "both") else "both"
        self.policy_name = policy_name
        self.events: list[dict[str, Any]] = []
        self.blocked = False

    # ---- pure decision logic (unit-testable without ADK objects) ----------

    def _decide(self, text: str, direction: str) -> tuple[str, str | None, str]:
        """Return ``(status, override_text, message)`` for a piece of text.

        ``status`` is ``passed`` / ``warned`` / ``failed``. ``override_text`` is
        the sanitized replacement when a fail-behavior masks/rewrites/falls back;
        ``None`` otherwise.
        """
        rules = {**self.rules, "mode": direction}
        result = validate_guardrail_content(text, rules)
        if result.passed:
            return ("passed", None, result.message)

        fail_behavior = rules.get("fail_behavior", "block")
        if fail_behavior in _OVERRIDE_BEHAVIORS:
            adjusted = apply_fail_behavior(
                result, fail_behavior, "workflow-policy", content=text, rules=rules
            )
            return ("warned", adjusted.output_override, adjusted.message)
        if fail_behavior == "warn":
            return ("warned", None, f"[WARN] {result.message}")
        # block (default) — recorded as a hard violation, enforced as a soft block.
        return ("failed", None, result.message)

    def _record(self, direction: str, status: str, message: str) -> None:
        self.events.append(
            {
                "node_id": "workflow-policy",
                "node_label": self.policy_name,
                "status": status,
                "message": (message or "")[:300],
                "mode": direction,
                "guardrail_type": self.rules.get("guardrail_type"),
                "fail_behavior": self.rules.get("fail_behavior", "block"),
                "scope": "workflow",
            }
        )
        if status == "failed":
            self.blocked = True

    # ---- ADK callbacks ----------------------------------------------------

    async def before_model_callback(
        self, *, callback_context: Any, llm_request: Any
    ) -> LlmResponse | None:
        if self.mode not in ("input", "both"):
            return None
        text = _contents_to_text(getattr(llm_request, "contents", None))
        if not text or not text.strip():
            return None
        status, _override, message = self._decide(text, "input")
        if status == "passed":
            return None
        self._record("input", status, message)
        if status == "failed":
            # Short-circuit: the agent "responds" with the block, model never runs.
            # Match the agent's expected serialization so schema validation passes.
            return _text_response(
                f"Blocked by workflow guardrail policy: {message}",
                as_json=_expects_json(llm_request),
            )
        # Input masking can't rewrite the request cleanly — warn and continue.
        return None

    async def after_model_callback(
        self, *, callback_context: Any, llm_response: Any
    ) -> LlmResponse | None:
        if self.mode not in ("output", "both"):
            return None
        raw = _response_text(llm_response)
        if not raw or not raw.strip():
            return None
        # Validate the decoded content; re-encode any replacement to match.
        content, was_json = _decode_str_response(raw)
        status, override, message = self._decide(content, "output")
        if status == "passed":
            return None
        self._record("output", status, message)
        if override is not None:
            return _text_response(override, as_json=was_json)
        if status == "failed":
            return _text_response(
                f"Blocked by workflow guardrail policy: {message}", as_json=was_json
            )
        return None  # warn — keep the original output
