import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.config import settings
from app.schemas.knowledge import KnowledgeBulkImport, KnowledgeDocumentCreate, KnowledgeDocumentResponse
from app.schemas.memory import WorkflowMemoryEntry, WorkflowMemoryResponse
from app.schemas.run import RunResponse
from app.schemas.workflow import (
    RunCompareResponse,
    ScheduledWorkflowInfo,
    WorkflowCreate,
    WorkflowImportIntoExisting,
    WorkflowImportPayload,
    WorkflowListItem,
    WorkflowResponse,
    WorkflowTriggerPayload,
    WorkflowUpdate,
    WorkflowVersionCreate,
    WorkflowVersionListItem,
    WorkflowVersionResponse,
)
from app.services.compiler import clear_compile_cache
from app.services.schedule_sync import sync_workflow_schedule
from app.services.executor import active_run_count, schedule_run
from app.services.run_concurrency import count_active_runs
from app.services.eval import compute_aggregate_score, scores_delta
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from app.services.job_queue import create_job
from app.services.knowledge_indexing import apply_embedding
from app.services.knowledge_jobs import enqueue_bulk_import, enqueue_reindex
from app.services.persistent_memory import clear_workflow_memory, load_workflow_memory, namespace_to_dict
from app.services.quality_metrics import aggregate_workflow_quality
from app.services.schedule_info import last_scheduled_run_at, list_user_scheduled_workflows, schedule_info_for_graph
from app.services.workflow_capabilities import workflow_needs_gemini
from app.services.workflow_import import WorkflowImportError, normalize_workflow_import

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _get_user_workflow(db: Session, workflow_id: UUID, user_id: UUID) -> models.Workflow:
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


def _latest_version(db: Session, workflow_id: UUID) -> models.WorkflowVersion | None:
    return (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowVersion.version_number.desc())
        .first()
    )


@router.get("", response_model=list[WorkflowListItem])
def list_workflows(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    version_stats = (
        db.query(
            models.WorkflowVersion.workflow_id.label("workflow_id"),
            func.count(models.WorkflowVersion.id).label("version_count"),
            func.max(models.WorkflowVersion.version_number).label("latest_version_number"),
        )
        .group_by(models.WorkflowVersion.workflow_id)
        .subquery()
    )

    rows = (
        db.query(
            models.Workflow,
            version_stats.c.version_count,
            version_stats.c.latest_version_number,
        )
        .outerjoin(version_stats, models.Workflow.id == version_stats.c.workflow_id)
        .filter(models.Workflow.user_id == user_id)
        .order_by(models.Workflow.updated_at.desc())
        .all()
    )

    return [
        WorkflowListItem(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            created_at=wf.created_at,
            updated_at=wf.updated_at,
            version_count=int(version_count or 0),
            latest_version_number=int(latest_version_number) if latest_version_number else None,
            published=wf.published_version_id is not None,
            is_external=(wf.description or "") == "External agent (ingested traces)",
        )
        for wf, version_count, latest_version_number in rows
    ]


@router.post("", response_model=WorkflowResponse)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        validate_workflow_graph(payload.graph_json)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    workflow = models.Workflow(
        name=payload.name,
        description=payload.description,
        user_id=user_id,
    )
    db.add(workflow)
    db.flush()

    version = models.WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        graph_json=payload.graph_json,
    )
    db.add(version)
    db.flush()
    sync_workflow_schedule(
        db,
        workflow_id=workflow.id,
        version_id=version.id,
        graph_json=payload.graph_json,
    )
    db.commit()
    db.refresh(workflow)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        webhook_url=workflow.webhook_url,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        latest_version=WorkflowVersionResponse.model_validate(version),
    )


@router.get("/schedules", response_model=list[ScheduledWorkflowInfo])
def list_scheduled_workflows(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """List workflows with schedule triggers and their next/last fire times."""
    rows = list_user_scheduled_workflows(db, user_id)
    return [ScheduledWorkflowInfo(**row) for row in rows]


@router.get("/eval-snippets")
def batch_eval_snippets(
    limit: int = Query(default=3, ge=1, le=10),
    per_workflow: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Recent eval history snippets for all user workflows in one request."""
    workflows = (
        db.query(models.Workflow.id)
        .filter(models.Workflow.user_id == user_id)
        .order_by(models.Workflow.updated_at.desc())
        .limit(limit)
        .all()
    )
    workflow_ids = [row[0] for row in workflows]
    if not workflow_ids:
        return {"snippets": {}}

    runs = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.node_results))
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(
            models.Workflow.user_id == user_id,
            models.WorkflowVersion.workflow_id.in_(workflow_ids),
        )
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(limit * per_workflow * 5)
        .all()
    )

    snippets: dict[str, list[dict]] = {str(wf_id): [] for wf_id in workflow_ids}
    for run in runs:
        wf_id = str(run.version.workflow_id) if run.version else None
        if not wf_id or wf_id not in snippets:
            continue
        if len(snippets[wf_id]) >= per_workflow:
            continue
        scores = _extract_run_eval_metrics(run)
        if not scores:
            continue
        metrics = run.metrics_json or {}
        snippets[wf_id].append(
            {
                "run_id": str(run.id),
                "created_at": run.created_at,
                "status": run.status,
                "input_text": run.input_text,
                "scores": scores,
                "eval_passed": metrics.get("eval_passed"),
                "eval_aggregate": metrics.get("eval_aggregate"),
                "guardrail_blocked": bool(metrics.get("guardrail_blocked")),
            }
        )

    return {"snippets": snippets}


@router.post("/import", response_model=WorkflowResponse)
def import_workflow(
    payload: WorkflowImportPayload,
    name_suffix: str | None = Query(default=None, description="Optional suffix appended to imported name"),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Create a new workflow from an aegis-workflow-v1 export JSON."""
    try:
        name, description, graph = normalize_workflow_import(payload.model_dump(exclude_none=True))
    except WorkflowImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if name_suffix:
        name = f"{name} {name_suffix}".strip()

    workflow = models.Workflow(
        name=name,
        description=description,
        user_id=user_id,
    )
    db.add(workflow)
    db.flush()

    version = models.WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        graph_json=graph,
    )
    db.add(version)
    db.flush()
    sync_workflow_schedule(db, workflow_id=workflow.id, version_id=version.id, graph_json=graph)
    db.commit()
    db.refresh(workflow)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        webhook_url=workflow.webhook_url,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        latest_version=WorkflowVersionResponse.model_validate(version),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)
    latest = _latest_version(db, workflow_id)
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        webhook_url=workflow.webhook_url,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        latest_version=WorkflowVersionResponse.model_validate(latest) if latest else None,
    )


@router.get("/{workflow_id}/quality")
def get_workflow_quality(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Per-workflow eval trends, guardrail health, and regression alerts."""
    workflow = _get_user_workflow(db, workflow_id, user_id)
    version = _latest_version(db, workflow_id)

    runs = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow))
        .join(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(50)
        .all()
    )

    graph_json = version.graph_json if version else None
    quality = aggregate_workflow_quality(runs, graph_json)
    quality["workflow_id"] = str(workflow.id)
    quality["workflow_name"] = workflow.name
    return quality


@router.get("/{workflow_id}/schedule", response_model=ScheduledWorkflowInfo)
def get_workflow_schedule(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)
    version = _latest_version(db, workflow_id)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    last_fired = last_scheduled_run_at(db, workflow_id)
    info = schedule_info_for_graph(
        workflow.id,
        workflow.name,
        version.graph_json,
        last_fired_at=last_fired,
    )
    if not info:
        raise HTTPException(status_code=404, detail="Workflow has no schedule trigger")
    return ScheduledWorkflowInfo(**info)


@router.post("/{workflow_id}/import", response_model=WorkflowVersionResponse)
def import_into_workflow(
    workflow_id: UUID,
    payload: WorkflowImportIntoExisting,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Replace or version the graph on an existing workflow from export JSON."""
    workflow = _get_user_workflow(db, workflow_id, user_id)

    try:
        _, _, graph = normalize_workflow_import(payload.model_dump(exclude_none=True))
    except WorkflowImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latest = _latest_version(db, workflow_id)
    # Never mutate a published version in place — fork a new version so
    # /v1/invoke keeps serving the pinned published graph (mirrors save_version).
    published_id = getattr(workflow, "published_version_id", None)
    must_fork = (
        payload.save_as_new_version
        or latest is None
        or (published_id is not None and latest is not None and latest.id == published_id)
    )
    if must_fork:
        version_number = (latest.version_number + 1) if latest else 1
        version = models.WorkflowVersion(
            workflow_id=workflow_id,
            version_number=version_number,
            graph_json=graph,
        )
        db.add(version)
        db.flush()
    else:
        latest.graph_json = graph
        version = latest

    sync_workflow_schedule(
        db,
        workflow_id=workflow_id,
        version_id=version.id,
        graph_json=version.graph_json,
    )
    db.commit()
    db.refresh(version)
    clear_compile_cache()
    return version


@router.get("/{workflow_id}/export")
def export_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)
    version = _latest_version(db, workflow_id)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    payload = {
        "format": "aegis-workflow-v1",
        "workflow_id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "version_number": version.version_number,
        "version_id": str(version.id),
        "graph_json": version.graph_json,
        "exported_at": version.created_at.isoformat(),
    }
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in workflow.name).strip("-") or "workflow"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-{workflow_id}.json"'},
    )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)

    if payload.name is not None:
        workflow.name = payload.name
    if payload.description is not None:
        workflow.description = payload.description
    if payload.webhook_url is not None:
        workflow.webhook_url = payload.webhook_url or None
    if payload.budget_json is not None:
        workflow.budget_json = payload.budget_json or None

    db.commit()
    db.refresh(workflow)
    latest = _latest_version(db, workflow_id)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        webhook_url=workflow.webhook_url,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        latest_version=WorkflowVersionResponse.model_validate(latest) if latest else None,
    )


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionListItem])
def list_versions(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    versions = (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowVersion.version_number.desc())
        .all()
    )
    return [
        WorkflowVersionListItem(
            id=version.id,
            workflow_id=version.workflow_id,
            version_number=version.version_number,
            created_at=version.created_at,
            node_count=len((version.graph_json or {}).get("nodes", [])),
        )
        for version in versions
    ]


@router.get("/{workflow_id}/versions/{version_id}", response_model=WorkflowVersionResponse)
def get_version(
    workflow_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    version = (
        db.query(models.WorkflowVersion)
        .filter(
            models.WorkflowVersion.id == version_id,
            models.WorkflowVersion.workflow_id == workflow_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{workflow_id}/versions", response_model=WorkflowVersionResponse)
def save_version(
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)

    try:
        validate_workflow_graph(payload.graph_json)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latest = _latest_version(db, workflow_id)
    # Never mutate a published version in place — fork a new version so
    # /v1/invoke keeps serving the pinned published graph.
    published_id = getattr(workflow, "published_version_id", None)
    must_fork = (
        payload.save_as_new_version
        or latest is None
        or (published_id is not None and latest is not None and latest.id == published_id)
    )
    if must_fork:
        version_number = (latest.version_number + 1) if latest else 1
        version = models.WorkflowVersion(
            workflow_id=workflow_id,
            version_number=version_number,
            graph_json=payload.graph_json,
        )
        db.add(version)
        db.flush()
    else:
        latest.graph_json = payload.graph_json
        version = latest

    sync_workflow_schedule(
        db,
        workflow_id=workflow_id,
        version_id=version.id,
        graph_json=version.graph_json,
    )
    db.commit()
    db.refresh(version)
    clear_compile_cache()
    return version


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse)
def duplicate_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)

    latest = _latest_version(db, workflow_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Workflow has no versions")

    copy = models.Workflow(
        name=f"{workflow.name} (copy)",
        description=workflow.description,
        user_id=user_id,
        webhook_url=workflow.webhook_url,
    )
    db.add(copy)
    db.flush()

    version = models.WorkflowVersion(
        workflow_id=copy.id,
        version_number=1,
        graph_json=latest.graph_json,
    )
    db.add(version)
    db.flush()
    sync_workflow_schedule(
        db,
        workflow_id=copy.id,
        version_id=version.id,
        graph_json=latest.graph_json,
    )
    db.commit()
    db.refresh(copy)

    return WorkflowResponse(
        id=copy.id,
        name=copy.name,
        description=copy.description,
        webhook_url=copy.webhook_url,
        created_at=copy.created_at,
        updated_at=copy.updated_at,
        latest_version=WorkflowVersionResponse.model_validate(version),
    )


def _flatten_eval_scores(raw_scores: dict) -> dict:
    scores = {
        "faithfulness": raw_scores.get("faithfulness"),
        "helpfulness": raw_scores.get("helpfulness"),
        "relevance": raw_scores.get("relevance"),
        "toxicity": raw_scores.get("toxicity"),
        "reasoning": raw_scores.get("reasoning", ""),
    }
    aggregate = raw_scores.get("aggregate_score")
    if aggregate is None:
        aggregate = compute_aggregate_score(scores)
    if aggregate is not None:
        scores["aggregate_score"] = aggregate
    return scores


def _extract_run_eval_metrics(run: models.WorkflowRun) -> dict | None:
    metrics = run.metrics_json or {}
    eval_rows = metrics.get("eval_scores") or []
    if eval_rows and isinstance(eval_rows[0], dict):
        scores = _flatten_eval_scores(eval_rows[0])
        aggregate = metrics.get("eval_aggregate")
        if aggregate is not None:
            scores["aggregate_score"] = aggregate
        return scores

    for node in run.node_results or []:
        if node.evaluation_scores:
            return _flatten_eval_scores(dict(node.evaluation_scores))
    return None


@router.get("/{workflow_id}/eval-history")
def eval_history(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)

    runs = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.node_results))
        .join(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(20)
        .all()
    )

    history = []
    for run in runs:
        scores = _extract_run_eval_metrics(run)
        if scores:
            metrics = run.metrics_json or {}
            history.append(
                {
                    "run_id": str(run.id),
                    "created_at": run.created_at,
                    "status": run.status,
                    "input_text": run.input_text,
                    "scores": scores,
                    "eval_passed": metrics.get("eval_passed"),
                    "eval_aggregate": metrics.get("eval_aggregate"),
                    "guardrail_blocked": bool(metrics.get("guardrail_blocked")),
                }
            )
    return history


@router.get("/{workflow_id}/compare-runs", response_model=RunCompareResponse)
def compare_runs(
    workflow_id: UUID,
    run_a: UUID = Query(...),
    run_b: UUID = Query(...),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)

    def load_run(run_id: UUID) -> models.WorkflowRun:
        run = (
            db.query(models.WorkflowRun)
            .options(
                joinedload(models.WorkflowRun.node_results),
                joinedload(models.WorkflowRun.version),
            )
            .filter(models.WorkflowRun.id == run_id)
            .first()
        )
        if not run or not run.version or run.version.workflow_id != workflow_id:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found for workflow")
        return run

    run_left = load_run(run_a)
    run_right = load_run(run_b)

    scores_a = _extract_run_eval_metrics(run_left)
    scores_b = _extract_run_eval_metrics(run_right)

    return RunCompareResponse(
        run_a_id=run_a,
        run_b_id=run_b,
        run_a_scores=scores_a,
        run_b_scores=scores_b,
        delta=scores_delta(scores_a, scores_b),
        run_a_output=run_left.final_output,
        run_b_output=run_right.final_output,
        run_a_version=run_left.version.version_number,
        run_b_version=run_right.version.version_number,
    )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = _get_user_workflow(db, workflow_id, user_id)

    # Run children (LlmCall/Feedback) have no FK cascade — delete them
    # explicitly before the runs, or Postgres raises and SQLite orphans rows.
    run_ids = [
        rid
        for (rid,) in db.query(models.WorkflowRun.id)
        .join(models.WorkflowVersion, models.WorkflowVersion.id == models.WorkflowRun.workflow_version_id)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .all()
    ]
    if run_ids:
        db.query(models.LlmCall).filter(models.LlmCall.run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Feedback).filter(models.Feedback.run_id.in_(run_ids)).delete(
            synchronize_session=False
        )

    # Dataset (+ items) and Experiment reference the workflow with no cascade.
    dataset_ids = [
        did
        for (did,) in db.query(models.Dataset.id)
        .filter(models.Dataset.workflow_id == workflow_id)
        .all()
    ]
    db.query(models.Experiment).filter(models.Experiment.workflow_id == workflow_id).delete(
        synchronize_session=False
    )
    if dataset_ids:
        db.query(models.DatasetItem).filter(
            models.DatasetItem.dataset_id.in_(dataset_ids)
        ).delete(synchronize_session=False)
        db.query(models.Dataset).filter(models.Dataset.workflow_id == workflow_id).delete(
            synchronize_session=False
        )

    db.query(models.WorkflowSchedule).filter(models.WorkflowSchedule.workflow_id == workflow_id).delete()
    db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.workflow_id == workflow_id).delete()
    db.query(models.WorkflowMemory).filter(models.WorkflowMemory.workflow_id == workflow_id).delete()
    db.query(models.BackgroundJob).filter(models.BackgroundJob.workflow_id == workflow_id).delete()
    db.query(models.ObservabilityRollup).filter(models.ObservabilityRollup.workflow_id == workflow_id).delete()
    clear_compile_cache()
    from app.services.audit import record_audit

    record_audit(db, user_id, "delete", "workflow", workflow_id, {"name": workflow.name})
    db.delete(workflow)
    db.commit()
    return None


@router.get("/{workflow_id}/memory", response_model=WorkflowMemoryResponse)
def get_workflow_memory(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    rows = load_workflow_memory(db, workflow_id)
    return WorkflowMemoryResponse(
        workflow_id=str(workflow_id),
        entries=[WorkflowMemoryEntry(**row) for row in rows],
        namespaces=namespace_to_dict(rows),
    )


@router.delete("/{workflow_id}/memory")
def delete_workflow_memory(
    workflow_id: UUID,
    namespace: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    deleted = clear_workflow_memory(db, workflow_id, namespace)
    return {"status": "cleared", "deleted": deleted, "namespace": namespace}


@router.get("/{workflow_id}/knowledge", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    rows = (
        db.query(models.KnowledgeDocument)
        .filter(models.KnowledgeDocument.workflow_id == workflow_id)
        .order_by(models.KnowledgeDocument.updated_at.desc())
        .all()
    )
    return [KnowledgeDocumentResponse.from_row(row) for row in rows]


@router.post("/{workflow_id}/knowledge", response_model=KnowledgeDocumentResponse)
def create_knowledge_document(
    workflow_id: UUID,
    payload: KnowledgeDocumentCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    row = models.KnowledgeDocument(
        workflow_id=workflow_id,
        title=payload.title,
        text=payload.text,
    )
    db.add(row)
    db.flush()
    apply_embedding(row, db)
    db.commit()
    db.refresh(row)
    return KnowledgeDocumentResponse.from_row(row)


@router.post("/{workflow_id}/knowledge/bulk")
async def bulk_import_knowledge(
    workflow_id: UUID,
    payload: KnowledgeBulkImport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    documents = [
        {"title": item.title, "text": item.text}
        for item in payload.documents
    ]
    job = create_job(
        db,
        job_type="knowledge_bulk_import",
        user_id=user_id,
        workflow_id=workflow_id,
        payload={"documents": documents},
    )
    background_tasks.add_task(enqueue_bulk_import, job.id)
    return {
        "status": "queued",
        "job_id": str(job.id),
        "document_count": len(documents),
        "workflow_id": str(workflow_id),
    }


@router.post("/{workflow_id}/knowledge/reindex")
async def reindex_knowledge(
    workflow_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    count = (
        db.query(func.count(models.KnowledgeDocument.id))
        .filter(models.KnowledgeDocument.workflow_id == workflow_id)
        .scalar()
        or 0
    )
    job = create_job(
        db,
        job_type="knowledge_reindex",
        user_id=user_id,
        workflow_id=workflow_id,
        payload={"count": count},
    )
    background_tasks.add_task(enqueue_reindex, job.id)
    return {
        "status": "queued",
        "job_id": str(job.id),
        "count": count,
        "workflow_id": str(workflow_id),
    }


@router.delete("/{workflow_id}/knowledge/{document_id}")
def delete_knowledge_document(
    workflow_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_workflow(db, workflow_id, user_id)
    row = (
        db.query(models.KnowledgeDocument)
        .filter(
            models.KnowledgeDocument.id == document_id,
            models.KnowledgeDocument.workflow_id == workflow_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": str(document_id)}


@router.post("/{workflow_id}/trigger", response_model=RunResponse)
async def trigger_workflow(
    workflow_id: UUID,
    payload: WorkflowTriggerPayload | None = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Start a workflow run from a webhook-style ingress (Lyzr SuperFlow / n8n Webhook)."""
    workflow = _get_user_workflow(db, workflow_id, user_id)
    version = _latest_version(db, workflow_id)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    body = payload.input if payload else None
    if isinstance(body, dict):
        input_text = json.dumps(body, ensure_ascii=False)
    elif body is not None:
        input_text = str(body)
    else:
        input_text = "{}"

    try:
        validate_workflow_graph(version.graph_json)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Mirror the /api/runs gate: trust the in-memory task count in "inline" mode
    # and fall back to a staleness-bounded DB count only in "worker" mode, so
    # orphaned pending/running rows cannot wedge the invoke path with 429s.
    in_memory_runs = active_run_count()
    if settings.run_execution_mode == "worker":
        active = max(in_memory_runs, count_active_runs(db))
    else:
        active = in_memory_runs
    if active >= settings.max_concurrent_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many concurrent runs (limit: {settings.max_concurrent_runs})",
        )

    if workflow_needs_gemini(version.graph_json) and not settings.google_api_key:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_API_KEY is not configured. Add it to .env to run LLM workflows.",
        )

    run = models.WorkflowRun(
        workflow_version_id=version.id,
        status="pending",
        input_text=input_text,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if settings.run_execution_mode != "worker":
        schedule_run(run.id)

    return RunResponse(
        id=run.id,
        workflow_version_id=run.workflow_version_id,
        status=run.status,
        input_text=run.input_text,
        final_output=run.final_output,
        metrics_json=run.metrics_json,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        node_results=[],
    )