"""Per-workflow budget enforcement: cost/day, runs/hour, tokens/run.

Budgets live on ``workflows.budget_json``:
    {"cost_usd_per_day": 5.0, "runs_per_hour": 60, "tokens_per_run": 200000}

Enforced pre-flight when a run is created (API and scheduler paths). A breach
returns a human-readable reason; callers surface it as HTTP 429 or skip the
scheduled fire.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db import models
from app.services.time_utils import to_db_utc


def check_workflow_budget(db: Session, workflow: models.Workflow) -> str | None:
    """Return a breach reason, or None when the run may proceed."""
    budget = workflow.budget_json or {}
    if not budget:
        return None

    now = datetime.now(timezone.utc)
    version_ids = [
        row[0]
        for row in db.query(models.WorkflowVersion.id)
        .filter(models.WorkflowVersion.workflow_id == workflow.id)
        .all()
    ]
    if not version_ids:
        return None

    runs_per_hour = budget.get("runs_per_hour")
    if runs_per_hour:
        hour_ago = to_db_utc(db, now - timedelta(hours=1))
        recent = (
            db.query(models.WorkflowRun)
            .filter(
                models.WorkflowRun.workflow_version_id.in_(version_ids),
                models.WorkflowRun.created_at >= hour_ago,
            )
            .count()
        )
        if recent >= int(runs_per_hour):
            return f"Budget exceeded: {recent} runs in the last hour (limit {runs_per_hour})"

    cost_per_day = budget.get("cost_usd_per_day")
    if cost_per_day:
        day_ago = to_db_utc(db, now - timedelta(days=1))
        rows = (
            db.query(models.WorkflowRun.metrics_json)
            .filter(
                models.WorkflowRun.workflow_version_id.in_(version_ids),
                models.WorkflowRun.created_at >= day_ago,
            )
            .all()
        )
        spent = 0.0
        for (metrics,) in rows:
            value = (metrics or {}).get("total_cost_usd")
            if isinstance(value, (int, float)):
                spent += float(value)
        if spent >= float(cost_per_day):
            return f"Budget exceeded: ${spent:.4f} spent in 24h (limit ${float(cost_per_day):.2f})"

    return None


def tokens_per_run_limit(workflow: models.Workflow) -> int | None:
    budget = workflow.budget_json or {}
    value = budget.get("tokens_per_run")
    return int(value) if value else None
