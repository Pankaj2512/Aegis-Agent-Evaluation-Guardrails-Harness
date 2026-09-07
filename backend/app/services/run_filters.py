"""Cross-database filters for workflow run list queries."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Query

from app.db import models


def run_has_eval(run: models.WorkflowRun) -> bool:
    metrics = run.metrics_json or {}
    return metrics.get("eval_aggregate") is not None


def run_eval_passed(run: models.WorkflowRun) -> bool | None:
    metrics = run.metrics_json or {}
    value = metrics.get("eval_passed")
    return value if isinstance(value, bool) else None


def run_guardrail_blocked(run: models.WorkflowRun) -> bool:
    metrics = run.metrics_json or {}
    return bool(metrics.get("guardrail_blocked"))


def filter_runs_by_has_eval(
    runs: list[models.WorkflowRun],
    *,
    has_eval: bool,
) -> list[models.WorkflowRun]:
    return [run for run in runs if run_has_eval(run) == has_eval]


def filter_runs_by_eval_passed(
    runs: list[models.WorkflowRun],
    *,
    eval_passed: bool,
) -> list[models.WorkflowRun]:
    return [run for run in runs if run_eval_passed(run) is eval_passed]


def filter_runs_by_guardrail_blocked(
    runs: list[models.WorkflowRun],
    *,
    guardrail_blocked: bool,
) -> list[models.WorkflowRun]:
    return [run for run in runs if run_guardrail_blocked(run) is guardrail_blocked]


def apply_run_quality_sql_filters(
    query: Query,
    *,
    has_eval: bool | None = None,
    eval_passed: bool | None = None,
    guardrail_blocked: bool | None = None,
) -> Query:
    metrics = models.WorkflowRun.metrics_json
    eval_aggregate = metrics["eval_aggregate"].as_string()
    if has_eval is not None:
        if has_eval:
            query = query.filter(
                metrics.isnot(None),
                eval_aggregate.isnot(None),
                eval_aggregate != "null",
            )
        else:
            query = query.filter(
                or_(
                    metrics.is_(None),
                    eval_aggregate.is_(None),
                    eval_aggregate == "null",
                )
            )
    if eval_passed is not None:
        eval_key = metrics["eval_passed"]
        if eval_passed:
            query = query.filter(eval_key.as_boolean().is_(True))
        else:
            query = query.filter(eval_key.as_boolean().is_(False))
    if guardrail_blocked is not None:
        guard_key = metrics["guardrail_blocked"]
        if guardrail_blocked:
            query = query.filter(guard_key.as_boolean().is_(True))
        else:
            query = query.filter(
                or_(guard_key.is_(None), guard_key.as_boolean().is_(False))
            )
    return query