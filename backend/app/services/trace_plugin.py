"""Per-run tool-call capture via ADK plugin callbacks (Trust-layer trace tree).

Mirrors ``TokenTrackerPlugin`` (which captures model calls) but for **tool
calls**: it hooks ``before/after/on_error_tool_callback`` to record each tool
invocation an agent makes — name, args, result/error, timing — keyed by the ADK
agent name. The executor maps agent names back to canvas node ids after the run
and writes these as ``tool_call`` child spans of their node span, so the
waterfall drills from a node into the agent's actual tool usage (previously a
black box).
"""

from __future__ import annotations

import time
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin


def _summarize(value: Any, limit: int = 2000) -> str | None:
    if value is None:
        return None
    try:
        import json

        text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001 — never let summarization break a run
        text = str(value)
    text = text.strip()
    if not text:
        return None
    return text[:limit]


class TracePlugin(BasePlugin):
    """Accumulates tool-call spans (name/args/result/timing) per ADK agent."""

    def __init__(self, max_chars: int = 2000) -> None:
        super().__init__(name="aegis_trace")
        self.max_chars = max_chars
        # Chronological tool-call records for the nested trace tree.
        self.tool_calls: list[dict[str, Any]] = []
        # Pending starts keyed by (invocation_id, agent, tool) so before/after pair up.
        self._pending: dict[tuple[str, str, str], dict[str, Any]] = {}

    @staticmethod
    def _agent_name(tool_context: Any) -> str:
        return str(getattr(tool_context, "agent_name", "") or "") or "unknown"

    @staticmethod
    def _key(tool_context: Any, tool: Any) -> tuple[str, str, str]:
        return (
            str(getattr(tool_context, "invocation_id", "") or ""),
            str(getattr(tool_context, "agent_name", "") or ""),
            str(getattr(tool, "name", "") or ""),
        )

    async def before_tool_callback(
        self, *, tool: Any, tool_args: dict[str, Any], tool_context: Any
    ) -> None:
        self._pending[self._key(tool_context, tool)] = {
            "agent": self._agent_name(tool_context),
            "name": str(getattr(tool, "name", "") or "tool"),
            "args": _summarize(tool_args, self.max_chars),
            "started_wall": time.time(),
        }
        return None

    async def after_tool_callback(
        self, *, tool: Any, tool_args: dict[str, Any], tool_context: Any, result: dict
    ) -> None:
        self._finish(tool_context, tool, status="completed", result=result)
        return None

    async def on_tool_error_callback(
        self, *, tool: Any, tool_args: dict[str, Any], tool_context: Any, error: Exception
    ) -> None:
        self._finish(tool_context, tool, status="failed", result=None, error=str(error))
        return None

    def _finish(
        self,
        tool_context: Any,
        tool: Any,
        *,
        status: str,
        result: Any,
        error: str | None = None,
    ) -> None:
        key = self._key(tool_context, tool)
        start = self._pending.pop(key, None)
        if start is None:
            # after without a matching before — synthesize a zero-duration span.
            start = {
                "agent": self._agent_name(tool_context),
                "name": str(getattr(tool, "name", "") or "tool"),
                "args": None,
                "started_wall": time.time(),
            }
        ended = time.time()
        self.tool_calls.append(
            {
                **start,
                "status": status,
                "result": _summarize(result, self.max_chars),
                "error": error,
                "ended_wall": ended,
                "latency_ms": int((ended - start["started_wall"]) * 1000),
            }
        )
