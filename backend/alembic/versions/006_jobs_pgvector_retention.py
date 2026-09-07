"""Background jobs, scheduler index, optional pgvector column.

Revision ID: 006_jobs_pgvector_retention
Revises: 005_schedule_last_fired
"""

from alembic import op
import sqlalchemy as sa

revision = "006_jobs_pgvector_retention"
down_revision = "005_schedule_last_fired"
branch_labels = None
depends_on = None

_ACTIVE_SCHEDULE_WHERE = sa.text("enabled IS TRUE AND cron_valid IS TRUE")


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])
    op.create_index("ix_background_jobs_user_id", "background_jobs", ["user_id"])
    op.create_index("ix_background_jobs_workflow_id", "background_jobs", ["workflow_id"])
    op.create_index(
        "ix_workflow_schedules_active",
        "workflow_schedules",
        ["enabled", "cron_valid"],
        postgresql_where=_ACTIVE_SCHEDULE_WHERE,
        sqlite_where=_ACTIVE_SCHEDULE_WHERE,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            """
            ALTER TABLE knowledge_documents
            ADD COLUMN IF NOT EXISTS embedding_vector vector(768)
            """
        )
    else:
        op.add_column(
            "knowledge_documents",
            sa.Column("embedding_vector", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS embedding_vector")
    else:
        op.drop_column("knowledge_documents", "embedding_vector")
    op.drop_index("ix_workflow_schedules_active", table_name="workflow_schedules")
    op.drop_index("ix_background_jobs_workflow_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_user_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_status", table_name="background_jobs")
    op.drop_index("ix_background_jobs_job_type", table_name="background_jobs")
    op.drop_table("background_jobs")