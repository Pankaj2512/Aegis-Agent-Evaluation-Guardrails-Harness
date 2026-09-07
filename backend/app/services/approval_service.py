"""Human-in-the-loop approval for paused workflow runs (Lyzr SuperFlow)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings

# Keys are "run_id" (legacy / single-waiter) or "run_id::node_id" so concurrent
# approval nodes in parallel branches do not share one Event.
_approval_events: dict[str, asyncio.Event] = {}
_approval_results: dict[str, dict[str, Any]] = {}


class HumanApprovalDenied(Exception):
    def __init__(self, node_id: str, comment: str = "") -> None:
        self.node_id = node_id
        self.comment = comment
        super().__init__(comment or f"Approval denied at node {node_id}")


class HumanApprovalTimeout(Exception):
    pass


def _approval_key(run_id: str, node_id: str | None = None) -> str:
    if node_id:
        return f"{run_id}::{node_id}"
    return run_id


def _keys_for_run(run_id: str) -> list[str]:
    """All in-memory keys belonging to a run (bare + per-node)."""
    prefix = f"{run_id}::"
    keys = [k for k in set(_approval_events) | set(_approval_results) if k == run_id or k.startswith(prefix)]
    return keys


def clear_approval_state(run_id: str, node_id: str | None = None) -> None:
    if node_id is not None:
        key = _approval_key(run_id, node_id)
        _approval_events.pop(key, None)
        _approval_results.pop(key, None)
        return
    for key in _keys_for_run(run_id):
        _approval_events.pop(key, None)
        _approval_results.pop(key, None)


def submit_approval(
    run_id: str,
    *,
    approved: bool,
    comment: str = "",
    node_id: str | None = None,
) -> None:
    result = {"approved": approved, "comment": comment}
    if node_id is not None:
        key = _approval_key(run_id, node_id)
        _approval_results[key] = result
        event = _approval_events.get(key)
        if event:
            event.set()
        # Also satisfy a legacy run_id-only waiter if present.
        legacy = _approval_events.get(run_id)
        if legacy and key != run_id:
            _approval_results[run_id] = result
            legacy.set()
        return

    # No node_id: deliver to every pending waiter for this run (and bare key).
    targets = _keys_for_run(run_id) or [run_id]
    if run_id not in targets:
        targets.append(run_id)
    for key in targets:
        _approval_results[key] = result
        event = _approval_events.get(key)
        if event:
            event.set()


async def wait_for_approval(
    run_id: str,
    *,
    node_id: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    key = _approval_key(run_id, node_id)
    existing = _approval_results.get(key)
    if existing is None and node_id is not None:
        # Early submit without node_id still satisfies a per-node wait.
        existing = _approval_results.get(run_id)
        if existing is not None:
            _approval_results.pop(run_id, None)
            _approval_events.pop(run_id, None)
            return existing
    if existing is not None:
        _approval_results.pop(key, None)
        _approval_events.pop(key, None)
        return existing

    limit = timeout if timeout is not None else float(settings.approval_timeout_seconds)
    event = _approval_events.setdefault(key, asyncio.Event())
    try:
        await asyncio.wait_for(event.wait(), timeout=limit)
    except asyncio.TimeoutError as exc:
        clear_approval_state(run_id, node_id)
        raise HumanApprovalTimeout(f"Approval timed out after {limit}s") from exc
    finally:
        _approval_events.pop(key, None)
    return _approval_results.pop(key, {"approved": False, "comment": "no decision"})
