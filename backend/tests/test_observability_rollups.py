from datetime import datetime, timezone
from uuid import uuid4

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.services.observability_rollups import aggregate_rollups_for_user


def test_leaderboard_run_count_uses_total_runs_not_eval_count():
    db = SessionLocal()
    workflow_id = uuid4()
    try:
        bucket = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        db.add(
            models.ObservabilityRollup(
                user_id=DEFAULT_DEV_USER_ID,
                workflow_id=workflow_id,
                bucket_hour=bucket,
                run_count=10,
                eval_count=4,
                eval_sum=16.0,
            )
        )
        db.commit()

        result = aggregate_rollups_for_user(db, DEFAULT_DEV_USER_ID)
        entry = next(
            row
            for row in result["workflow_eval_leaderboard"]
            if row["workflow_id"] == str(workflow_id)
        )
        assert entry["run_count"] == 10
        assert entry["avg_eval_score"] == 4.0
    finally:
        db.query(models.ObservabilityRollup).filter(
            models.ObservabilityRollup.workflow_id == workflow_id
        ).delete()
        db.commit()
        db.close()