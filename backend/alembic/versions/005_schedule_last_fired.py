"""Persist scheduler dedup timestamp on workflow schedules.

Revision ID: 005_schedule_last_fired
Revises: 004_perf_rollups_index
"""

from alembic import op
import sqlalchemy as sa

revision = "005_schedule_last_fired"
down_revision = "004_perf_rollups_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_schedules",
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_schedules", "last_fired_at")