import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import assist, credentials, eval_presets, jobs, meta, node_test, observability, runs, templates, workflows, datasets, experiments, feedback, guardrail_policies, alerts, platform
from app.config import settings
from app.http_client import shutdown_http_client, startup_http_client
from app.logging_config import configure_logging
from app.services.executor import active_run_count, shutdown_active_runs
from app.services.rate_limit import check_rate_limit, rate_limited_path
from app.services.run_worker import run_worker_status, stop_run_worker
from app.services.schedule_worker import scheduler_status, start_schedule_worker, stop_schedule_worker
from app.db import models
from app.db.database import SessionLocal
from app.services.tracing import init_tracing, install_http_middleware, is_tracing_enabled, shutdown_tracing
from app.services.startup import check_database, run_startup_tasks

import logging

configure_logging(settings.log_level)
logger = logging.getLogger("aegis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.async_tasks import set_main_loop

    init_tracing()
    # NOTE: schema is owned by Alembic (single source of truth). We intentionally
    # do NOT call Base.metadata.create_all here — run_startup_tasks() instead
    # gates boot on migrations being current (see services/startup.py).
    startup_status = run_startup_tasks()
    app.state.startup_status = startup_status
    set_main_loop(asyncio.get_running_loop())
    await startup_http_client()
    start_schedule_worker()
    # Do NOT start the in-process run worker here. In "worker" execution mode a
    # dedicated worker.py process owns run claiming/execution; starting the loop
    # here too would let both the API and the worker claim the same pending runs
    # (split-brain double-claim). In "inline" mode create_run schedules runs
    # directly, so no polling worker is needed either.
    # NOTE (single-process constraint): SSE streams and human-approval waits live
    # in the executor's in-memory broker/approval state. When runs execute in the
    # separate worker process, /stream and /approve served by the API process
    # cannot see that state. Cross-process streams/approvals require a shared
    # transport (out of scope for this fix).
    yield
    set_main_loop(None)
    await stop_run_worker()
    await stop_schedule_worker()
    await shutdown_active_runs()
    await shutdown_http_client()
    shutdown_tracing()


app = FastAPI(title="Aegis API", version="0.4.0", lifespan=lifespan)
install_http_middleware(app)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
allow_credentials = bool(origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(eval_presets.router)
app.include_router(credentials.router)
app.include_router(workflows.router)
app.include_router(node_test.router)
app.include_router(runs.router)
app.include_router(templates.router)
app.include_router(observability.router)
app.include_router(jobs.router)
app.include_router(datasets.router)
app.include_router(experiments.router)
app.include_router(feedback.router)
app.include_router(guardrail_policies.router)
app.include_router(alerts.router)
app.include_router(platform.router)
app.include_router(assist.router)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if rate_limited_path(request.url.path):
        check_rate_limit(request)
    return await call_next(request)


@app.middleware("http")
async def viewer_role_middleware(request: Request, call_next):
    """RBAC-lite: viewer keys are read-only across all mutating API methods."""
    if (
        settings.auth_enabled
        and (
            request.url.path.startswith("/api/")
            or request.url.path.startswith("/v1/")
        )
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
    ):
        from fastapi.responses import JSONResponse as _JSONResponse

        from app.auth.deps import _resolve_api_token, role_from_api_key

        token = _resolve_api_token(
            request.headers.get("authorization"),
            request.headers.get("x-aegis-api-key"),
            request.query_params.get("api_key"),
        )
        if role_from_api_key(token) == "viewer":
            return _JSONResponse(
                status_code=403, content={"detail": "Viewer keys are read-only"}
            )
    return await call_next(request)


def _health_db_counts() -> tuple[int, int]:
    db = SessionLocal()
    try:
        pending_runs = (
            db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.status.in_(["pending", "queued"]))
            .count()
        )
        queued_jobs = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.status == "queued")
            .count()
        )
        return pending_runs, queued_jobs
    finally:
        db.close()


@app.get("/health")
async def health(request: Request):
    db_ok = await asyncio.to_thread(check_database)
    startup_status = getattr(request.app.state, "startup_status", {})
    status = "ok" if db_ok else "degraded"

    pending_runs = 0
    queued_jobs = 0
    if db_ok:
        pending_runs, queued_jobs = await asyncio.to_thread(_health_db_counts)

    return {
        "status": status,
        "service": "aegis-backend",
        "version": "0.4.0",
        "auth_enabled": settings.auth_enabled,
        "database_ok": db_ok,
        "stale_runs_recovered": startup_status.get("stale_runs_recovered", 0),
        "stale_jobs_recovered": startup_status.get("stale_jobs_recovered", 0),
        "scheduler": scheduler_status(),
        "run_worker": run_worker_status(),
        "active_runs": active_run_count(),
        "pending_runs": pending_runs,
        "queued_jobs": queued_jobs,
        "max_concurrent_runs": settings.max_concurrent_runs,
        "tracing_enabled": is_tracing_enabled(),
        "tracing_ui_base_url": settings.otel_ui_base_url or None,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        extra={"event": "unhandled_exception"},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )