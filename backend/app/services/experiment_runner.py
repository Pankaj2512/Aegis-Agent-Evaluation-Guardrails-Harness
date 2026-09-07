"""Batch experiments: run a dataset against workflow version(s), score, compare.

An experiment of kind "batch" runs one version over every dataset item and
aggregates eval/cost/latency. Kind "regression" runs candidate and baseline
versions over the same items and renders a verdict — the gate a CI pipeline
calls before promoting a version.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import models
from app.db.database import SessionLocal
from app.services.executor import execute_run

logger = logging.getLogger("aegis.experiments")

# Bounded parallelism: experiments share the executor with interactive runs.
_ITEM_CONCURRENCY = 2

# Regression defaults: candidate fails the gate if avg eval drops more than
# this, or if it introduces new failures.
DEFAULT_MAX_EVAL_DROP = 0.5


def _session():
    return SessionLocal(expire_on_commit=False)


async def _run_one_item(
    version_id: uuid.UUID, input_text: str, semaphore: asyncio.Semaphore
) -> dict[str, Any]:
    async with semaphore:
        db = _session()
        try:
            run = models.WorkflowRun(
                workflow_version_id=version_id,
                status="pending",
                input_text=input_text,
            )
            db.add(run)
            db.commit()
            run_id = run.id
        finally:
            db.close()

        try:
            await execute_run(run_id)
        except Exception as exc:  # noqa: BLE001 — item failures land in the summary
            logger.warning("Experiment item crashed", extra={"run_id": str(run_id), "error": str(exc)})

        db = _session()
        try:
            done = db.query(models.WorkflowRun).filter(models.WorkflowRun.id == run_id).first()
            metrics = (done.metrics_json or {}) if done else {}
            return {
                "run_id": str(run_id),
                "input": input_text[:300],
                "status": done.status if done else "failed",
                "output": (done.final_output or "")[:500] if done else None,
                "eval_aggregate": metrics.get("eval_aggregate"),
                "latency_ms": metrics.get("latency_ms"),
                "cost_usd": metrics.get("total_cost_usd"),
                "total_tokens": metrics.get("total_tokens"),
            }
        finally:
            db.close()


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evals = [r["eval_aggregate"] for r in rows if isinstance(r.get("eval_aggregate"), (int, float))]
    latencies = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))]
    costs = [r["cost_usd"] for r in rows if isinstance(r.get("cost_usd"), (int, float))]
    failures = sum(1 for r in rows if r.get("status") != "completed")
    return {
        "items": len(rows),
        "failures": failures,
        "failure_rate": round(failures / len(rows), 3) if rows else 0.0,
        "avg_eval": round(sum(evals) / len(evals), 2) if evals else None,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
        "total_cost_usd": round(sum(costs), 6) if costs else None,
    }


async def _run_version_over_items(
    version_id: uuid.UUID, items: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(_ITEM_CONCURRENCY)
    rows = await asyncio.gather(
        *[_run_one_item(version_id, input_text, semaphore) for _, input_text in items]
    )
    for (item_id, _), row in zip(items, rows):
        row["item_id"] = item_id
    return list(rows)


async def run_experiment(experiment_id: uuid.UUID) -> None:
    db = _session()
    try:
        exp = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
        if not exp:
            return
        items = [
            (str(item.id), item.input_text)
            for item in db.query(models.DatasetItem)
            .filter(models.DatasetItem.dataset_id == exp.dataset_id)
            .order_by(models.DatasetItem.created_at)
            .all()
        ]
        exp.status = "running"
        db.commit()
        kind = exp.kind
        version_id = exp.version_id
        baseline_version_id = exp.baseline_version_id
        options = dict(exp.summary_json or {})  # regression options stashed at creation
    finally:
        db.close()

    summary: dict[str, Any] = {}
    status = "completed"
    try:
        if not items:
            raise ValueError("Dataset has no items")

        candidate_rows = await _run_version_over_items(version_id, items)
        summary = {
            "candidate": {"version_id": str(version_id), **_aggregate(candidate_rows)},
            "rows": candidate_rows,
        }

        if kind == "regression" and baseline_version_id:
            baseline_rows = await _run_version_over_items(baseline_version_id, items)
            baseline_agg = _aggregate(baseline_rows)
            candidate_agg = summary["candidate"]
            max_drop = float(options.get("max_eval_drop") or DEFAULT_MAX_EVAL_DROP)

            eval_delta = None
            if candidate_agg.get("avg_eval") is not None and baseline_agg.get("avg_eval") is not None:
                eval_delta = round(candidate_agg["avg_eval"] - baseline_agg["avg_eval"], 2)
            failure_delta = candidate_agg["failures"] - baseline_agg["failures"]

            passed = True
            reasons: list[str] = []
            # Missing scores must not silently pass the gate (audit P2).
            if candidate_agg.get("avg_eval") is None or baseline_agg.get("avg_eval") is None:
                passed = False
                reasons.append("missing eval scores on candidate or baseline; gate cannot pass")
            elif eval_delta is not None and eval_delta < -max_drop:
                passed = False
                reasons.append(f"avg eval dropped {abs(eval_delta)} (limit {max_drop})")
            if failure_delta > 0:
                passed = False
                reasons.append(f"{failure_delta} new failure(s)")

            summary["baseline"] = {"version_id": str(baseline_version_id), **baseline_agg}
            summary["baseline_rows"] = baseline_rows
            summary["verdict"] = {
                "passed": passed,
                "eval_delta": eval_delta,
                "failure_delta": failure_delta,
                "max_eval_drop": max_drop,
                "reasons": reasons or ["no regression detected"],
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Experiment failed", extra={"experiment_id": str(experiment_id)})
        status = "failed"
        summary = {"error": str(exc), **summary}

    db = _session()
    try:
        exp = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
        if exp:
            exp.status = status
            exp.summary_json = summary
            exp.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
