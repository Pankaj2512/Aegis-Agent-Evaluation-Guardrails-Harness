"""Performance: partial active-run index and observability rollups.

Revision ID: 004_perf_rollups_index
Revises: 003_performance_indexes
"""

from alembic import op
import sqlalchemy as sa

revision = "004_perf_rollups_index"
down_revision = "003"
branch_labels = None
depends_on = None

_ACTIVE_RUN_WHERE = sa.text("status IN ('pending', 'running', 'awaiting_approval')")


def upgrade() -> None:
    op.create_index(
        "ix_workflow_runs_active_status",
        "workflow_runs",
        ["status"],
        postgresql_where=_ACTIVE_RUN_WHERE,
        sqlite_where=_ACTIVE_RUN_WHERE,
    )
    op.create_table(
        "observability_rollups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("bucket_hour", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eval_sum", sa.Float(), nullable=False, server_default="0"),
        sa.Column("eval_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guardrail_blocked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "workflow_id", "bucket_hour", name="uq_observability_rollups_bucket"),
    )
    op.create_index("ix_observability_rollups_user_id", "observability_rollups", ["user_id"])
    op.create_index("ix_observability_rollups_workflow_id", "observability_rollups", ["workflow_id"])
    op.create_index("ix_observability_rollups_bucket_hour", "observability_rollups", ["bucket_hour"])


def downgrade() -> None:
    op.drop_index("ix_observability_rollups_bucket_hour", table_name="observability_rollups")
    op.drop_index("ix_observability_rollups_workflow_id", table_name="observability_rollups")
    op.drop_index("ix_observability_rollups_user_id", table_name="observability_rollups")
    op.drop_table("observability_rollups")
    op.drop_index("ix_workflow_runs_active_status", table_name="workflow_runs")