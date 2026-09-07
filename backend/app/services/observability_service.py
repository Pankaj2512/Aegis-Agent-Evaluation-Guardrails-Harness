"""Optimized observability queries and response builders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import models
from app.services.executor import active_run_count
from app.services.observability_rollups import (
    aggregate_rollups_for_user,
    enrich_leaderboard_names,
    merge_rollup_quality,
)
from app.services.quality_metrics import aggregate_quality_metrics, enrich_run_summary
from app.services.schedule_info import list_user_scheduled_workflows
from app.services.schedule_worker import scheduler_status
from app.services.tracing import is_tracing_enabled

_SUMMARY_RUN_LIMIT = 100


def _user_workflow_ids(db: Session, user_id: UUID) -> list[UUID]:
    rows = db.query(models.Workflow.id).filter(models.Workflow.user_id == user_id).all()
    return [row[0] for row in rows]


def _user_runs_query(
    db: Session, user_id: UUID, *, limit: int = _SUMMARY_RUN_LIMIT, search: str | None = None
):
    query = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow))
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.Workflow.user_id == user_id)
    )
    if search and search.strip():
        needle = f"%{search.strip()}%"
        query = query.filter(
            models.WorkflowRun.input_text.ilike(needle)
            | models.WorkflowRun.final_output.ilike(needle)
        )
    return query.order_by(models.WorkflowRun.created_at.desc()).limit(limit)


def _load_summary_runs(db: Session, user_id: UUID) -> tuple[dict[str, Any], list[models.WorkflowRun]]:
    rollup_totals = aggregate_rollups_for_user(db, user_id)
    runs = _user_runs_query(db, user_id, limit=_SUMMARY_RUN_LIMIT).all()
    return rollup_totals, runs


def build_overview(
    db: Session,
    user_id: UUID,
    *,
    rollup_totals: dict[str, Any] | None = None,
    runs: list[models.WorkflowRun] | None = None,
) -> dict[str, Any]:
    workflow_ids = _user_workflow_ids(db, user_id)
    workflow_count = len(workflow_ids)

    knowledge_doc_count = 0
    memory_entry_count = 0
    if workflow_ids:
        knowledge_doc_count = (
            db.query(func.count(models.KnowledgeDocument.id))
            .filter(models.KnowledgeDocument.workflow_id.in_(workflow_ids))
            .scalar()
            or 0
        )
        memory_entry_count = (
            db.query(func.count(models.WorkflowMemory.id))
            .filter(models.WorkflowMemory.workflow_id.in_(workflow_ids))
            .scalar()
            or 0
        )

    if rollup_totals is None or runs is None:
        loaded_rollups, loaded_runs = _load_summary_runs(db, user_id)
        rollup_totals = rollup_totals if rollup_totals is not None else loaded_rollups
        runs = runs if runs is not None else loaded_runs

    status_counts: dict[str, int] = dict(rollup_totals.get("status_counts") or {})
    eval_scores: list[float] = []
    total_latency = 0
    latency_count = 0

    for run in runs:
        if not rollup_totals["run_count"]:
            status_counts[run.status] = status_counts.get(run.status, 0) + 1
        metrics = run.metrics_json or {}
        if metrics.get("eval_aggregate") is not None:
            eval_scores.append(float(metrics["eval_aggregate"]))
        if metrics.get("latency_ms") is not None:
            total_latency += int(metrics["latency_ms"])
            latency_count += 1

    run_count = rollup_totals["run_count"] or len(runs)
    avg_eval = rollup_totals.get("avg_eval_score")
    if avg_eval is None and eval_scores:
        avg_eval = round(sum(eval_scores) / len(eval_scores), 2)

    return {
        "workflow_count": workflow_count,
        "run_count": run_count,
        "status_counts": status_counts,
        "avg_eval_score": avg_eval,
        "avg_latency_ms": round(total_latency / latency_count) if latency_count else None,
        "knowledge_doc_count": knowledge_doc_count,
        "memory_entry_count": memory_entry_count,
        "scheduled_workflow_count": (
            db.query(func.count(models.WorkflowSchedule.id))
            .join(models.Workflow, models.Workflow.id == models.WorkflowSchedule.workflow_id)
            .filter(models.Workflow.user_id == user_id, models.WorkflowSchedule.enabled.is_(True))
            .scalar()
            or 0
        ),
        "scheduled_workflows": list_user_scheduled_workflows(db, user_id),
        "active_runs": active_run_count(),
        "max_concurrent_runs": settings.max_concurrent_runs,
        "scheduler": scheduler_status(),
        "tracing": {
            "enabled": is_tracing_enabled(),
            "ui_base_url": settings.otel_ui_base_url or None,
        },
    }


def build_quality(
    db: Session,
    user_id: UUID,
    *,
    rollup_totals: dict[str, Any] | None = None,
    runs: list[models.WorkflowRun] | None = None,
) -> dict[str, Any]:
    if rollup_totals is None or runs is None:
        loaded_rollups, loaded_runs = _load_summary_runs(db, user_id)
        rollup_totals = rollup_totals if rollup_totals is not None else loaded_rollups
        runs = runs if runs is not None else loaded_runs

    recent_quality = aggregate_quality_metrics(runs)
    merged = merge_rollup_quality(rollup_totals, recent_quality)
    leaderboard = enrich_leaderboard_names(
        db,
        merged.get("workflow_eval_leaderboard") or rollup_totals.get("workflow_eval_leaderboard") or [],
    )
    merged["workflow_eval_leaderboard"] = leaderboard
    return merged


def build_recent_runs(
    db: Session, user_id: UUID, *, limit: int = 20, search: str | None = None
) -> list[dict[str, Any]]:
    runs = _user_runs_query(db, user_id, limit=limit, search=search).all()
    return [enrich_run_summary(r) for r in runs]


def build_summary(db: Session, user_id: UUID) -> dict[str, Any]:
    rollup_totals, runs = _load_summary_runs(db, user_id)
    overview = build_overview(db, user_id, rollup_totals=rollup_totals, runs=runs)
    overview["quality"] = build_quality(db, user_id, rollup_totals=rollup_totals, runs=runs)
    overview["recent_runs"] = [enrich_run_summary(r) for r in runs[:20]]
    return overview


# ---------------------------------------------------------------------------
# Dashboards: dimension breakdowns + latency percentiles over a filtered window
# ---------------------------------------------------------------------------

_DASHBOARD_RUN_LIMIT = 2000


def _percentiles(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    ordered = sorted(values)
    n = len(ordered)

    def _pct(p: float) -> int:
        # Nearest-rank with the standard "round up" rule so median of 2 is
        # the lower value when p*n is integer (avoids always picking max).
        if n == 1:
            return ordered[0]
        rank = max(1, int(p * n + 0.999999999))  # ceil without importing math edge cases
        if p * n == int(p * n):
            rank = max(1, int(p * n))
        return ordered[min(n - 1, rank - 1)]

    return {"p50": _pct(0.50), "p95": _pct(0.95), "p99": _pct(0.99)}


def build_dashboards(
    db: Session,
    user_id: UUID,
    *,
    status: str | None = None,
    workflow_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """Dimension breakdowns (workflow / node_type / model) + latency percentiles.

    Computed over a filtered WorkflowRun window (with LlmCall for the model
    dimension). Filters — status / date range / workflow — are accepted so the
    frontend can persist them in the URL.
    """
    run_query = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow))
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.Workflow.user_id == user_id)
    )
    if status:
        run_query = run_query.filter(models.WorkflowRun.status == status)
    if workflow_id:
        run_query = run_query.filter(models.Workflow.id == workflow_id)
    if start_date:
        run_query = run_query.filter(models.WorkflowRun.created_at >= start_date)
    if end_date:
        run_query = run_query.filter(models.WorkflowRun.created_at <= end_date)

    runs = (
        run_query.order_by(models.WorkflowRun.created_at.desc())
        .limit(_DASHBOARD_RUN_LIMIT)
        .all()
    )
    run_ids = [run.id for run in runs]

    latencies: list[int] = []
    total_cost = 0.0
    total_tokens = 0
    status_counts: dict[str, int] = {}
    by_workflow: dict[str, dict[str, Any]] = {}

    for run in runs:
        workflow = run.version.workflow if run.version else None
        metrics = run.metrics_json or {}
        status_counts[run.status] = status_counts.get(run.status, 0) + 1

        lat = metrics.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(int(lat))
        cost = metrics.get("total_cost_usd")
        tokens = metrics.get("total_tokens")

        wf_key = str(workflow.id) if workflow else "unknown"
        bucket = by_workflow.setdefault(
            wf_key,
            {
                "workflow_id": str(workflow.id) if workflow else None,
                "workflow_name": workflow.name if workflow else "unknown",
                "run_count": 0,
                "failed_count": 0,
                "cost_usd": 0.0,
                "total_tokens": 0,
            },
        )
        bucket["run_count"] += 1
        if run.status == "failed":
            bucket["failed_count"] += 1
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
            bucket["cost_usd"] = round(bucket["cost_usd"] + float(cost), 6)
        if isinstance(tokens, (int, float)):
            total_tokens += int(tokens)
            bucket["total_tokens"] += int(tokens)

    # By node_type — from NodeResult rows of the windowed runs.
    by_node_type: dict[str, dict[str, Any]] = {}
    if run_ids:
        from sqlalchemy import case

        node_rows = (
            db.query(
                models.NodeResult.node_type,
                func.count(models.NodeResult.id).label("count"),
                func.sum(func.coalesce(models.NodeResult.latency_ms, 0)).label("latency_sum"),
                func.sum(case((models.NodeResult.status == "failed", 1), else_=0)).label("failed"),
            )
            .filter(models.NodeResult.run_id.in_(run_ids))
            .group_by(models.NodeResult.node_type)
            .all()
        )
        for node_type, count, latency_sum, failed in node_rows:
            count = int(count or 0)
            by_node_type[node_type] = {
                "node_type": node_type,
                "count": count,
                "failed_count": int(failed or 0),
                "avg_latency_ms": round(int(latency_sum or 0) / count) if count else None,
            }

    # By model — from LlmCall rows of the windowed runs.
    by_model: dict[str, dict[str, Any]] = {}
    if run_ids:
        from sqlalchemy import case

        model_rows = (
            db.query(
                models.LlmCall.model,
                func.count(models.LlmCall.id).label("calls"),
                func.sum(func.coalesce(models.LlmCall.total_tokens, 0)).label("tokens"),
                func.sum(func.coalesce(models.LlmCall.cost_usd, 0.0)).label("cost"),
                func.sum(func.coalesce(models.LlmCall.latency_ms, 0)).label("latency_sum"),
            )
            .filter(models.LlmCall.run_id.in_(run_ids))
            .group_by(models.LlmCall.model)
            .all()
        )
        for model, calls, tokens, cost, latency_sum in model_rows:
            calls = int(calls or 0)
            by_model[model or "unknown"] = {
                "model": model or "unknown",
                "call_count": calls,
                "total_tokens": int(tokens or 0),
                "cost_usd": round(float(cost or 0.0), 6),
                "avg_latency_ms": round(int(latency_sum or 0) / calls) if calls else None,
            }

    pct = _percentiles(latencies)

    return {
        "filters": {
            "status": status,
            "workflow_id": str(workflow_id) if workflow_id else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "run_count": len(runs),
        "status_counts": status_counts,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "latency_ms": {
            "p50": pct["p50"],
            "p95": pct["p95"],
            "p99": pct["p99"],
            "sample_size": len(latencies),
        },
        "by_workflow": sorted(
            by_workflow.values(), key=lambda w: w["run_count"], reverse=True
        ),
        "by_node_type": sorted(
            by_node_type.values(), key=lambda n: n["count"], reverse=True
        ),
        "by_model": sorted(by_model.values(), key=lambda m: m["call_count"], reverse=True),
    }


# ---------------------------------------------------------------------------
# Trust: single consistent-window source for the unified Trust dashboard
# ---------------------------------------------------------------------------

_TRUST_RUN_LIMIT = 500


def build_trust(db: Session, user_id: UUID, *, limit: int = _TRUST_RUN_LIMIT) -> dict[str, Any]:
    """One consistent-window source for the Trust dashboard's SLO tiles.

    Every rate — eval pass, guardrail block, failure — is computed over the
    SAME recent-run scan, so a tile never divides a recent numerator by an
    all-time denominator (which silently understates block/failure rates).
    Cost, latency percentiles, and the top-workflow breakdown come from the
    same window so the whole surface tells one coherent story.
    """
    rows = (
        db.query(
            models.WorkflowRun.metrics_json,
            models.WorkflowRun.status,
            models.Workflow.name,
        )
        .join(
            models.WorkflowVersion,
            models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id,
        )
        .join(models.Workflow, models.WorkflowVersion.workflow_id == models.Workflow.id)
        .filter(models.Workflow.user_id == user_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )

    runs_scanned = len(rows)
    failed_runs = 0
    eval_evaluated = 0
    eval_passed = 0
    eval_failed = 0
    eval_sum = 0.0
    eval_score_count = 0
    guardrail_blocked_runs = 0
    guardrail_events = {"passed": 0, "warned": 0, "failed": 0}
    eval_trend_desc: list[float] = []
    latencies: list[int] = []
    total_cost = 0.0
    total_tokens = 0
    by_workflow: dict[str, dict[str, Any]] = {}

    for metrics, status, name in rows:
        metrics = metrics or {}

        if status == "failed":
            failed_runs += 1

        aggregate = metrics.get("eval_aggregate")
        if aggregate is not None:
            eval_evaluated += 1
            if metrics.get("eval_passed") is True:
                eval_passed += 1
            elif metrics.get("eval_passed") is False:
                eval_failed += 1
            try:
                eval_sum += float(aggregate)
                eval_score_count += 1
                eval_trend_desc.append(float(aggregate))
            except (TypeError, ValueError):
                pass

        if metrics.get("guardrail_blocked"):
            guardrail_blocked_runs += 1
        events = metrics.get("guardrail_events") or []
        for event in events:
            if isinstance(event, dict) and event.get("status") in guardrail_events:
                guardrail_events[event["status"]] += 1
        if not events and metrics.get("failed_guardrails"):
            guardrail_events["failed"] += len(metrics["failed_guardrails"])

        lat = metrics.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(int(lat))
        cost = metrics.get("total_cost_usd")
        tokens = metrics.get("total_tokens")
        wf = by_workflow.setdefault(
            name, {"workflow": name, "runs": 0, "cost_usd": 0.0, "failures": 0}
        )
        wf["runs"] += 1
        if status == "failed":
            wf["failures"] += 1
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
            wf["cost_usd"] = round(wf["cost_usd"] + float(cost), 6)
        if isinstance(tokens, (int, float)):
            total_tokens += int(tokens)

    latencies.sort()

    def _pct(p: float) -> int | None:
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, int(p * len(latencies)))]

    def _rate(num: int, den: int) -> float | None:
        return round(num / den, 4) if den else None

    # Pass rate only over runs with an explicit pass/fail verdict; scored runs
    # without thresholds (eval_passed is null) must not count as failures.
    eval_verdict_total = eval_passed + eval_failed
    return {
        "runs_scanned": runs_scanned,
        "window_limit": limit,
        "eval_evaluated": eval_evaluated,
        "eval_passed": eval_passed,
        "eval_failed": eval_failed,
        "eval_pass_rate": _rate(eval_passed, eval_verdict_total),
        "avg_eval": round(eval_sum / eval_score_count, 3) if eval_score_count else None,
        # Chronological (oldest→newest) tail for the pass-rate sparkline.
        "eval_trend": list(reversed(eval_trend_desc))[-30:],
        "guardrail_blocked_runs": guardrail_blocked_runs,
        "guardrail_block_rate": _rate(guardrail_blocked_runs, runs_scanned),
        "guardrail_events": {**guardrail_events, "total": sum(guardrail_events.values())},
        "failed_runs": failed_runs,
        "failure_rate": _rate(failed_runs, runs_scanned),
        "latency_p50_ms": _pct(0.50),
        "latency_p95_ms": _pct(0.95),
        "latency_p99_ms": _pct(0.99),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "top_workflows_by_cost": sorted(
            by_workflow.values(), key=lambda w: w["cost_usd"], reverse=True
        )[:8],
    }


# ---------------------------------------------------------------------------
# Guardrail violation drill-down (Trust dashboard, Phase 4.3)
# ---------------------------------------------------------------------------

_VIOLATION_STATUSES = frozenset({"warned", "failed"})


def build_guardrail_violations(db: Session, user_id: UUID, *, limit: int = _TRUST_RUN_LIMIT) -> dict[str, Any]:
    """Structured guardrail-violation drill-down over a recent-run window.

    Breaks guardrail events down by *type* (rules / presidio / prompt_injection
    / moderation / llm), not just severity totals, and returns a recent
    violation log so the Trust surface can answer "what is being blocked, by
    which rail, and where". Events predating type capture bucket as "unknown".
    """
    rows = (
        db.query(
            models.WorkflowRun.id,
            models.WorkflowRun.created_at,
            models.WorkflowRun.metrics_json,
            models.Workflow.name,
        )
        .join(
            models.WorkflowVersion,
            models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id,
        )
        .join(models.Workflow, models.WorkflowVersion.workflow_id == models.Workflow.id)
        .filter(models.Workflow.user_id == user_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )

    by_type: dict[str, dict[str, Any]] = {}
    wf_violations: dict[str, dict[str, Any]] = {}
    recent: list[dict[str, Any]] = []
    total_events = 0
    total_violations = 0

    for run_id, created_at, metrics, name in rows:
        metrics = metrics or {}
        run_violations = 0
        events = metrics.get("guardrail_events") or []
        if not events and metrics.get("failed_guardrails"):
            # Older runs recorded only failed_guardrails (no typed events); surface
            # them as unknown-type failures so the drill-down matches the Safety tile.
            events = [
                {"status": "failed", "guardrail_type": "unknown", "node_label": nid, "message": ""}
                for nid in metrics["failed_guardrails"]
            ]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            total_events += 1
            gtype = ev.get("guardrail_type") or "unknown"
            status = ev.get("status") or "unknown"
            bucket = by_type.setdefault(
                gtype, {"type": gtype, "passed": 0, "warned": 0, "failed": 0, "total": 0}
            )
            bucket["total"] += 1
            if status in bucket:
                bucket[status] += 1
            if status in _VIOLATION_STATUSES:
                total_violations += 1
                run_violations += 1
                if len(recent) < 50:
                    recent.append(
                        {
                            "run_id": str(run_id),
                            "workflow": name,
                            "node_label": ev.get("node_label"),
                            "type": gtype,
                            "status": status,
                            "message": (ev.get("message") or "")[:300],
                            "created_at": created_at.isoformat() if created_at else None,
                        }
                    )
        if run_violations:
            wf = wf_violations.setdefault(name, {"workflow": name, "violations": 0, "runs": 0})
            wf["violations"] += run_violations
            wf["runs"] += 1

    by_type_list = sorted(
        by_type.values(), key=lambda t: t["failed"] + t["warned"], reverse=True
    )
    for entry in by_type_list:
        entry["violations"] = entry["failed"] + entry["warned"]

    return {
        "runs_scanned": len(rows),
        "window_limit": limit,
        "total_events": total_events,
        "total_violations": total_violations,
        "by_type": by_type_list,
        "top_workflows": sorted(
            wf_violations.values(), key=lambda w: w["violations"], reverse=True
        )[:8],
        "recent": recent[:30],
    }