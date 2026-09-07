import asyncio
import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.db import models
from app.db.database import SessionLocal
from app.services.job_queue import create_job, dispatch_job


@pytest.mark.asyncio
async def test_dispatch_job_runs_once_on_concurrent_calls():
    workflow_id = uuid4()
    calls = {"count": 0}

    def slow_import(_workflow_id, _documents):
        time.sleep(0.05)
        calls["count"] += 1
        return 1

    db = SessionLocal()
    try:
        job = create_job(
            db,
            job_type="knowledge_bulk_import",
            workflow_id=workflow_id,
            payload={"documents": [{"text": "hello"}]},
        )
        job_id = job.id
    finally:
        db.close()

    with patch("app.services.knowledge_jobs.run_bulk_import_job", slow_import):
        await asyncio.gather(dispatch_job(job_id), dispatch_job(job_id))

    assert calls["count"] == 1

    db = SessionLocal()
    try:
        finished = db.query(models.BackgroundJob).filter(models.BackgroundJob.id == job_id).first()
        assert finished is not None
        assert finished.status == "completed"
    finally:
        db.close()