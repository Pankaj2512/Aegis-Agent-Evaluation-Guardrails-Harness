"""Wrap compiled node callables to maintain workflow context across execution.

The wrapper also bridges app-level routing to ADK 2.x: decision nodes
(IF/switch/router/classifier/filter/guardrail-in-route-mode) return
RouterDecision/ClassifierDecision objects, but ADK 2.x routes exclusively on
``ctx.route`` — a returned pydantic model is treated as plain output and every
routed edge goes dark. The wrapper accepts the ADK Context (injected for the
parameter named ``ctx``), sets ``ctx.route`` from the decision, and passes the
node's *input* through as output so content keeps flowing down the chosen
branch.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any

from app.services.guardrail import GuardrailResult
from app.services.routing_models import ClassifierDecision, RouterDecision

# Route emitted down a node's error edge when it fails and carries one. The
# frontend tags the outgoing error edge with ``data.route == "error"``.
ERROR_ROUTE = "error"

# Sentinel route stamped on a node's *success* edges (in the compiler) when that
# node also has an error branch. Those edges would otherwise be unconditional
# (``route=None``), which ADK fires even when the node routed down the error
# edge. Making them conditional on this sentinel keeps success and error paths
# mutually exclusive.
SUCCESS_ROUTE = "__ok__"


def _normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, GuardrailResult):
        return value.message or ("passed" if value.passed else "blocked")
    return str(value)


def wrap_with_context(
    node_id: str,
    fn: Callable[..., Any],
    context_ref: dict[str, Any],
    *,
    label: str | None = None,
    node_type: str | None = None,
    retries: int = 0,
    retry_delay_sec: float = 1.0,
    timeout_sec: float | None = None,
    error_branch: bool = False,
) -> Callable[..., Any]:
    """Record upstream input and node output in the shared workflow context,
    applying the node's reliability policy (retries with backoff + timeout)
    and translating decision objects into ADK route signals.

    ``error_branch`` marks a node that carries an outgoing error edge. When set,
    a failure that survives the retry policy is caught here instead of bubbling
    up and failing the whole run: the node is recorded as failed (for honest
    telemetry, via ``context_ref["_error_routed"]``), ``ctx.route`` is set to
    ``ERROR_ROUTE`` so execution continues only down the error edge, and the
    branch receives a JSON error payload as its input. On success, ``ctx.route``
    is set to ``SUCCESS_ROUTE`` (the sentinel the compiler stamped on this
    node's success edges) so the error edge is not taken.
    """
    is_coro = inspect.iscoroutinefunction(fn)

    def _record(node_input: str, output: str) -> str:
        context_ref["last_output"] = str(node_input)
        context_ref.setdefault("steps", {})[node_id] = {
            "output": output,
            "label": label or node_id,
            "type": node_type,
        }
        context_ref["last_output"] = output
        return output

    def _record_step_output(step_output: str, emitted: str) -> str:
        """Record a distinct step output while emitting a different value.

        Used by the run-from-here trigger passthrough: the trigger's recorded
        ``steps[trigger].output`` stays the raw run input (what the trigger
        genuinely received), while the value that flows downstream as
        ``last_output`` — and the trigger's emitted node output — is the pinned
        seed. This keeps ``{{steps.<trigger>.output}}`` honest (raw input) and
        ``{{last_output}}`` pinned.
        """
        context_ref.setdefault("steps", {})[node_id] = {
            "output": step_output,
            "label": label or node_id,
            "type": node_type,
        }
        context_ref["last_output"] = emitted
        return emitted

    async def _call_with_policy(node_input: str) -> Any:
        """Run fn under timeout, retrying transient failures with backoff."""
        attempt = 0
        while True:
            try:
                if is_coro:
                    coro = fn(node_input)
                else:
                    coro = asyncio.to_thread(fn, node_input)
                if timeout_sec:
                    return await asyncio.wait_for(coro, timeout=timeout_sec)
                return await coro
            except Exception as exc:  # noqa: BLE001 — retry policy is intentionally broad
                emit = context_ref.get("_emit")
                if attempt >= retries:
                    raise
                attempt += 1
                if callable(emit):
                    try:
                        await emit(
                            {
                                "type": "node_retry",
                                "node_id": node_id,
                                "node_label": label or node_id,
                                "attempt": attempt,
                                "max_attempts": retries,
                                "error": str(exc)[:200],
                            }
                        )
                    except Exception:
                        pass
                await asyncio.sleep(retry_delay_sec * (2 ** (attempt - 1)))

    async def wrapped(ctx, node_input: str) -> Any:
        # Run-from-here with pinned upstreams: the pruned graph rewires
        # trigger→start, but the trigger passthrough would overwrite the seeded
        # last_output with the raw run input. Prefer the seeded value so
        # {{last_output}} and positional input to the start node match pins.
        seeded = context_ref.get("_seeded_last_output")
        if node_type == "trigger" and seeded is not None:
            if ctx is not None and error_branch:
                ctx.route = SUCCESS_ROUTE
            # Emit the pinned seed downstream, but record the trigger's own
            # step output as the raw run input so {{steps.<trigger>.output}}
            # still reflects what the run was actually invoked with.
            return _record_step_output(str(node_input), str(seeded))

        context_ref["last_output"] = str(node_input)
        try:
            result = await _call_with_policy(node_input)
        except Exception as exc:  # noqa: BLE001 — error-branch routing
            if not error_branch:
                raise
            # The node failed and carries an error edge: route down it instead
            # of failing the run. Telemetry stays honest — the executor reads
            # ``_error_routed`` and records this node's NodeResult as failed.
            message = str(exc)
            context_ref.setdefault("_error_routed", {})[node_id] = {
                "error": message,
                "node_type": node_type,
            }
            if ctx is not None:
                ctx.route = ERROR_ROUTE
            payload = json.dumps(
                {"error": message, "node_id": node_id, "node_type": node_type},
                ensure_ascii=False,
            )
            return _record(node_input, payload)

        if isinstance(result, (RouterDecision, ClassifierDecision)):
            # ADK 2.x routes exclusively via ctx.route; the returned decision
            # object alone no longer selects an edge.
            if ctx is not None:
                ctx.route = str(result.route)
            context_ref.setdefault("routes", {})[node_id] = {
                "route": str(result.route),
                "reasoning": result.reasoning,
            }
            # Decision nodes are pass-through: downstream receives the content.
            return _record(node_input, str(node_input))

        # Plain success. When this node carries an error branch, its success
        # edges were compiled to the SUCCESS_ROUTE sentinel, so signal it so
        # they fire (and the error edge does not).
        if error_branch and ctx is not None:
            ctx.route = SUCCESS_ROUTE
        return _record(node_input, _normalize_output(result))

    wrapped.__name__ = getattr(fn, "__name__", node_id)
    return wrapped
