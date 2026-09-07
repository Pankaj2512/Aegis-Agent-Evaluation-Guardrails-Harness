from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import models
from app.db.database import SessionLocal, engine
from app.services.compiler import clear_compile_cache

logger = logging.getLogger("aegis.startup")

STALE_RUN_MESSAGE = "Run interrupted by server restart or crash"
STALE_JOB_MESSAGE = "Job interrupted by server restart or crash"


def check_database() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


class MigrationsBehindError(RuntimeError):
    """Raised when the database is behind the latest Alembic revision."""


def _alembic_head_revisions() -> set[str]:
    """Resolve the current Alembic head revision(s) from alembic/versions."""
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    return set(script.get_heads())


def _current_db_revisions() -> set[str]:
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return set(context.get_current_heads())


def check_migrations_current(*, strict: bool = True) -> bool:
    """Compare the DB's Alembic revision to head; log loudly / refuse to boot if behind.

    Mirrors the graceful-degradation posture used elsewhere: if the check itself
    cannot run (e.g. DB unreachable) we log and return False rather than crash.
    When ``strict`` is True (production default) a behind/unstamped database
    raises ``MigrationsBehindError`` so the app refuses to boot on drift.
    """
    try:
        heads = _alembic_head_revisions()
        current = _current_db_revisions()
    except Exception:
        logger.exception("Could not determine Alembic migration state")
        return False

    if current == heads:
        return True

    detail = (
        f"Database is not at the latest Alembic revision. "
        f"db={sorted(current) or '<none/unstamped>'} expected_head={sorted(heads)}. "
        f"Run `alembic upgrade head` before starting the app."
    )
    logger.error(detail, extra={"event": "migrations_behind"})
    if strict:
        raise MigrationsBehindError(detail)
    return False


def recover_stale_runs(*, force: bool = False) -> int:
    """Mark orphaned pending/running runs as failed after a crash or deploy.

    Guard for "worker" execution mode: run execution lives in a separate
    worker.py process, so an API-process restart must NOT force-fail runs the
    worker is actively executing. In that mode we leave in-flight runs alone
    unless ``force=True`` (used by the worker process on its own boot).
    """
    from app.config import settings

    if not force and getattr(settings, "run_execution_mode", "inline") == "worker":
        return 0

    db = SessionLocal()
    try:
        stale = (
            db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.status.in_(["pending", "running", "queued", "awaiting_approval"]))
            .all()
        )
        if not stale:
            return 0

        now = datetime.now(timezone.utc)
        for run in stale:
            run.status = "failed"
            run.final_output = STALE_RUN_MESSAGE
            run.completed_at = now
            if not run.started_at:
                run.started_at = now

        db.commit()
        logger.warning(
            "Recovered stale runs",
            extra={"count": len(stale), "event": "stale_runs_recovered"},
        )
        return len(stale)
    finally:
        db.close()


def recover_stale_jobs() -> int:
    """Mark orphaned running jobs as failed after a crash or deploy."""
    db = SessionLocal()
    try:
        stale = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.status == "running")
            .all()
        )
        if not stale:
            return 0

        now = datetime.now(timezone.utc)
        for job in stale:
            job.status = "failed"
            job.error = STALE_JOB_MESSAGE
            job.completed_at = now
            if not job.started_at:
                job.started_at = now

        db.commit()
        logger.warning(
            "Recovered stale jobs",
            extra={"count": len(stale), "event": "stale_jobs_recovered"},
        )
        return len(stale)
    finally:
        db.close()


def run_startup_tasks() -> dict[str, int | bool]:
    from app.config import settings

    clear_compile_cache()
    db_ok = check_database()

    migrations_current = True
    if db_ok and getattr(settings, "migration_check_enabled", True):
        # Gate startup on migrations being current. Strict mode raises
        # MigrationsBehindError (refuse to boot) unless explicitly disabled.
        migrations_current = check_migrations_current(
            strict=getattr(settings, "migration_check_strict", True)
        )

    recovered_runs = recover_stale_runs() if db_ok else 0
    recovered_jobs = recover_stale_jobs() if db_ok else 0
    return {
        "database_ok": db_ok,
        "migrations_current": migrations_current,
        "stale_runs_recovered": recovered_runs,
        "stale_jobs_recovered": recovered_jobs,
    }