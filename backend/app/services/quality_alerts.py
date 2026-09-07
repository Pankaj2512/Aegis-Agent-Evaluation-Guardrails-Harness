"""Dispatch workflow webhooks for quality events (eval fail, guardrail block)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db import models
from app.services.async_tasks import schedule_task
from app.services.webhook import dispatch_webhook

logger = logging.getLogger("aegis.quality")


def schedule_quality_webhook(
    workflow: models.Workflow | None,
    run: models.WorkflowRun,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    if not workflow or not workflow.webhook_url:
        return

    payload = {
        "event": event,
        "run_id": str(run.id),
        "workflow_id": str(workflow.id),
        "workflow_name": workflow.name,
        "status": run.status,
        "final_output": run.final_output,
        "metrics": run.metrics_json,
        "details": details or {},
    }
    schedule_task(dispatch_webhook(workflow.webhook_url, payload))
    logger.info(
        "Quality webhook scheduled",
        extra={"event": event, "run_id": str(run.id), "workflow_id": str(workflow.id)},
    )


def quality_webhook_for_run(
    workflow_id: UUID | None,
    run: models.WorkflowRun,
    workflow: models.Workflow | None = None,
) -> None:
    metrics = run.metrics_json or {}
    if metrics.get("guardrail_blocked"):
        schedule_quality_webhook(
            workflow,
            run,
            "quality.guardrail_blocked",
            {"failed_guardrails": metrics.get("failed_guardrails")},
        )
        return

    if metrics.get("eval_passed") is False:
        schedule_quality_webhook(
            workflow,
            run,
            "quality.eval_failed",
            {
                "eval_aggregate": metrics.get("eval_aggregate"),
                "eval_scores": metrics.get("eval_scores"),
            },
        )