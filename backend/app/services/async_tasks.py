"""Helpers for fire-and-forget asyncio tasks with exception logging."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger("aegis.async_tasks")


def _log_task_failure(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("Background task failed", exc_info=exc)


def schedule_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any] | None:
    """Schedule ``coro`` on the running event loop.

    When called from a worker thread with no running loop (e.g. alert evaluation
    via ``asyncio.to_thread``), fall back to ``run_coroutine_threadsafe`` against
    the main loop if one was registered, else log and drop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        task = loop.create_task(coro)
        task.add_done_callback(_log_task_failure)
        return task

    # Called from a thread without a running loop — try the main loop.
    main = _main_loop
    if main is not None and main.is_running():
        fut = asyncio.run_coroutine_threadsafe(coro, main)

        def _log_future(f: Any) -> None:
            try:
                exc = f.exception()
            except Exception:  # noqa: BLE001
                return
            if exc is not None:
                logger.exception("Background task failed", exc_info=exc)

        fut.add_done_callback(_log_future)
        return None

    logger.error(
        "schedule_task called with no running event loop; dropping coroutine %s",
        getattr(coro, "__name__", type(coro).__name__),
    )
    coro.close()
    return None


_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Register the process main loop for cross-thread schedule_task calls."""
    global _main_loop
    _main_loop = loop