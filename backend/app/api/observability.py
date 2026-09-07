import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db.database import get_db
from app.services.observability_events import stream_observability_events
from app.services.observability_service import (
    build_dashboards,
    build_guardrail_violations,
    build_overview,
    build_quality,
    build_recent_runs,
    build_summary,
    build_trust,
)

router = APIRouter(prefix="/api/observability", tags=["observability"])


@router.get("/summary")
def observability_summary(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return build_summary(db, user_id)


@router.get("/overview")
def observability_overview(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return build_overview(db, user_id)


@router.get("/quality")
def observability_quality(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return build_quality(db, user_id)


@router.get("/trust")
def observability_trust(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Unified Trust surface: eval / guardrail / failure / cost / latency SLOs
    over one consistent recent-run window (see build_trust)."""
    return build_trust(db, user_id)


@router.get("/violations")
def observability_violations(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Guardrail violation drill-down: events by type + a recent violation log."""
    return build_guardrail_violations(db, user_id)


@router.get("/runs")
def observability_runs(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
):
    return {"recent_runs": build_recent_runs(db, user_id, limit=limit, search=search)}


@router.get("/errors")
def observability_errors(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(default=200, ge=10, le=1000),
):
    """Failure clusters: recent failed runs grouped by normalized error signature."""
    import re as _re
    from app.db import models as _models

    rows = (
        db.query(_models.WorkflowRun, _models.Workflow.name)
        .join(_models.WorkflowVersion, _models.WorkflowRun.workflow_version_id == _models.WorkflowVersion.id)
        .join(_models.Workflow, _models.WorkflowVersion.workflow_id == _models.Workflow.id)
        .filter(_models.Workflow.user_id == user_id, _models.WorkflowRun.status == "failed")
        .order_by(_models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    clusters: dict[str, dict] = {}
    for run, workflow_name in rows:
        raw = (run.final_output or "unknown error").strip()
        # Normalize: strip UUIDs, hex ids, and numbers so identical failures cluster.
        signature = _re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", raw)
        signature = _re.sub(r"\d+", "<n>", signature)[:200]
        entry = clusters.setdefault(
            signature,
            {"signature": signature, "count": 0, "workflows": set(), "last_seen": None, "sample_run_id": str(run.id)},
        )
        entry["count"] += 1
        entry["workflows"].add(workflow_name)
        seen = run.created_at.isoformat() if run.created_at else None
        if seen and (entry["last_seen"] is None or seen > entry["last_seen"]):
            entry["last_seen"] = seen
            entry["sample_run_id"] = str(run.id)
    result = sorted(clusters.values(), key=lambda c: c["count"], reverse=True)
    for cluster in result:
        cluster["workflows"] = sorted(cluster["workflows"])[:5]
    return {"clusters": result[:20], "failed_runs_scanned": len(rows)}


def _parse_iso_date(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid {field} (expected ISO 8601)"
        ) from exc


@router.get("/dashboards")
def observability_dashboards(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    status: str | None = Query(default=None),
    workflow_id: UUID | None = Query(default=None),
    start_date: str | None = Query(default=None, description="ISO 8601 start of window"),
    end_date: str | None = Query(default=None, description="ISO 8601 end of window"),
):
    """Dimension breakdowns (by workflow / node_type / model) + latency p50/p95/p99.

    Filters (status / workflow_id / start_date / end_date) are URL-persistable.
    """
    return build_dashboards(
        db,
        user_id,
        status=status,
        workflow_id=workflow_id,
        start_date=_parse_iso_date(start_date, "start_date"),
        end_date=_parse_iso_date(end_date, "end_date"),
    )


@router.get("/costs")
def observability_costs(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(default=500, ge=50, le=2000),
):
    """Cost + latency operational view computed from recent runs."""
    from app.db import models as _models

    rows = (
        db.query(
            _models.WorkflowRun.metrics_json,
            _models.WorkflowRun.status,
            _models.Workflow.name,
            _models.WorkflowVersion.version_number,
        )
        .join(_models.WorkflowVersion, _models.WorkflowRun.workflow_version_id == _models.WorkflowVersion.id)
        .join(_models.Workflow, _models.WorkflowVersion.workflow_id == _models.Workflow.id)
        .filter(_models.Workflow.user_id == user_id)
        .order_by(_models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    latencies: list[int] = []
    total_cost = 0.0
    total_tokens = 0
    by_workflow: dict[str, dict] = {}
    version_evals: dict[str, dict[int, list[float]]] = {}
    for metrics, status, name, version_number in rows:
        metrics = metrics or {}
        lat = metrics.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(int(lat))
        cost = metrics.get("total_cost_usd")
        wf = by_workflow.setdefault(name, {"workflow": name, "runs": 0, "cost_usd": 0.0, "failures": 0})
        wf["runs"] += 1
        if status == "failed":
            wf["failures"] += 1
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
            wf["cost_usd"] = round(wf["cost_usd"] + float(cost), 6)
        tokens = metrics.get("total_tokens")
        if isinstance(tokens, (int, float)):
            total_tokens += int(tokens)
        eval_score = metrics.get("eval_aggregate")
        if isinstance(eval_score, (int, float)) and version_number is not None:
            version_evals.setdefault(name, {}).setdefault(int(version_number), []).append(float(eval_score))

    latencies.sort()

    def _pct(p: float) -> int | None:
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, int(p * len(latencies)))]

    version_trend = [
        {
            "workflow": name,
            "versions": [
                {"version": v, "avg_eval": round(sum(scores) / len(scores), 2), "runs": len(scores)}
                for v, scores in sorted(buckets.items())
            ],
        }
        for name, buckets in version_evals.items()
        if len(buckets) > 0
    ]

    return {
        "runs_scanned": len(rows),
        "latency_p50_ms": _pct(0.50),
        "latency_p95_ms": _pct(0.95),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "top_workflows_by_cost": sorted(by_workflow.values(), key=lambda w: w["cost_usd"], reverse=True)[:8],
        "version_eval_trend": version_trend[:8],
    }


@router.get("/stream")
async def stream_observability(
    user_id: UUID = Depends(get_current_user_id),
):
    async def event_generator():
        async for event in stream_observability_events(str(user_id)):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")