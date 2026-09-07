"""Mutable workflow context passed through node execution."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


class WorkflowContext:
    """Accumulates run input and per-step outputs for expression mapping."""

    def __init__(self, input_text: str, *, parsed_input: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = {
            "input": parsed_input if parsed_input is not None else {"text": input_text},
            "steps": {},
            "last_output": input_text,
            "memory": {},
        }

    @classmethod
    def from_input(cls, input_text: str) -> WorkflowContext:
        stripped = (input_text or "").strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return cls(input_text, parsed_input={**parsed, "text": input_text})
            except json.JSONDecodeError:
                pass
        return cls(input_text)

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def snapshot(self, *, max_output_chars: int = 500) -> dict[str, Any]:
        # Exclude underscore-prefixed runtime plumbing (hooks, ids, kb docs)
        # injected into the live dict by the executor — they are not user data
        # and are not JSON-serializable.
        data = deepcopy({k: v for k, v in self._data.items() if not k.startswith("_")})
        steps = data.get("steps")
        if isinstance(steps, dict):
            for step in steps.values():
                if not isinstance(step, dict) or "output" not in step:
                    continue
                output = str(step.get("output") or "")
                if len(output) > max_output_chars:
                    step["output"] = f"{output[:max_output_chars]}…"
        return data

    def snapshot_for_metrics(self, *, max_output_chars: int = 500) -> dict[str, Any]:
        """Snapshot safe for metrics/SSE — excludes workflow memory."""
        data = self.snapshot(max_output_chars=max_output_chars)
        data.pop("memory", None)
        return data

    def set_last_output(self, value: str) -> None:
        self._data["last_output"] = value

    def record_step(
        self,
        node_id: str,
        output: str,
        *,
        label: str | None = None,
        node_type: str | None = None,
    ) -> None:
        self._data["steps"][node_id] = {
            "output": output,
            "label": label or node_id,
            "type": node_type,
        }
        self._data["last_output"] = output