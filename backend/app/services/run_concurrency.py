"""Concurrency accounting for workflow runs.

The concurrency gate must reflect runs that could *plausibly still be
executing* — not every row ever left in a non-terminal state. Runs execute
in-process as asyncio tasks (see ``executor.active_run_count``); a
``pending``/``running`` row with no live task — orphaned by a crash, a restart,
or a scheduled fire that never progressed — can never resume. Counting those
rows lets a handful of zombies permanently exhaust ``max_concurrent_runs`` and
``429`` every future run (the failure this module fixes).

Two guards:

* :func:`count_active_runs` bounds the DB count by a staleness window so
  orphans age out of the gate.
* :func:`sweep_stale_runs` marks orphaned rows terminal, complementing
  ``startup.recover_stale_runs`` for long-lived processes where scheduled
  fires can accumulate pending rows over days.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.services.time_utils import db_utcnow, to_db_utc

logger = logging.getLogger("aegis.run_concurrency")

ACTIVE_STATUSES = ("pending", "running")
STALE_RUN_MESSAGE = "Run interrupted by server restart or crash"


def _stale_cutoff(db: Session) -> datetime:
    # A floor keeps a misconfigured tiny window from culling live runs.
    window = max(60, getattr(settings, "run_stale_after_seconds", 900))
    return to_db_utc(db, datetime.now(timezone.utc) - timedelta(seconds=window))


def count_active_runs(db: Session) -> int:
    """Count runs that could still be executing, ignoring stale orphans.

    In ``inline`` mode the authoritative signal is the in-memory task count
    (``executor.active_run_count``); this DB count is the cross-process signal
    used in ``worker`` mode. Either way, rows older than the staleness window
    are excluded so orphaned pending/running runs cannot wedge the gate.
    """
    return (
        db.query(func.count(models.WorkflowRun.id))
        .filter(models.WorkflowRun.status.in_(ACTIVE_STATUSES))
        .filter(models.WorkflowRun.created_at >= _stale_cutoff(db))
        .scalar()
        or 0
    )


def sweep_stale_runs(db: Session) -> int:
    """Mark orphaned pending/running runs (older than the staleness window) as
    failed, returning the count swept.

    Skips runs that still have a live in-process asyncio task (inline mode
    after a long human-approval pause), so a post-approval ``running`` row is
    not thrashing ``failed``→``completed``. Also treats ``awaiting_approval``
    as non-stale while younger than the approval timeout budget.
    """
    from app.services.executor import active_run_ids

    cutoff = _stale_cutoff(db)
    approval_window = max(
        60, int(getattr(settings, "approval_timeout_seconds", 3600) or 3600)
    )
    approval_cutoff = to_db_utc(
        db, datetime.now(timezone.utc) - timedelta(seconds=approval_window)
    )

    live_ids = active_run_ids()
    candidates = (
        db.query(models.WorkflowRun)
        .filter(
            models.WorkflowRun.status.in_(
                (*ACTIVE_STATUSES, "awaiting_approval", "queued")
            )
        )
        .filter(models.WorkflowRun.created_at < cutoff)
        .all()
    )
    stale = []
    for run in candidates:
        if run.id in live_ids or str(run.id) in live_ids:
            continue
        # Approval-parked runs may legitimately outlive run_stale_after_seconds.
        if run.status == "awaiting_approval" and run.created_at and run.created_at >= approval_cutoff:
            continue
        stale.append(run)
    if not stale:
        return 0

    now = db_utcnow(db)
    for run in stale:
        run.status = "failed"
        run.final_output = STALE_RUN_MESSAGE
        run.completed_at = now
        if not run.started_at:
            run.started_at = now

    db.commit()
    logger.warning(
        "Swept stale runs to failed",
        extra={"count": len(stale), "event": "stale_runs_swept"},
    )
    return len(stale)
