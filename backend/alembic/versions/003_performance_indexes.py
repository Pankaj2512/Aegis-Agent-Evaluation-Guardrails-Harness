"""Performance indexes for hot query paths

Revision ID: 003
Revises: 002
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
    op.create_index(
        "ix_workflow_versions_workflow_version",
        "workflow_versions",
        ["workflow_id", "version_number"],
    )
    op.create_index(
        "ix_workflow_runs_workflow_version_id",
        "workflow_runs",
        ["workflow_version_id"],
    )
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])
    op.create_index("ix_node_results_run_id", "node_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_node_results_run_id", table_name="node_results")
    op.drop_index("ix_workflow_runs_created_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_version_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_versions_workflow_version", table_name="workflow_versions")
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")