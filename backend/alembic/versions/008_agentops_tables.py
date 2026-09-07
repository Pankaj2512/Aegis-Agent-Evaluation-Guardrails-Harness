"""AgentOps: llm_calls, datasets, experiments, feedback, policies, alerts, audit + workflow publish/budget columns.

Revision ID: 008_agentops_tables
Revises: 007_pgvector_hnsw_index
"""

import sqlalchemy as sa
from alembic import op

revision = "008_agentops_tables"
down_revision = "007_pgvector_hnsw_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New tables are created by Base.metadata.create_all on startup; this
    # migration only covers columns added to existing tables.
    op.add_column("workflows", sa.Column("published_version_id", sa.Uuid(), nullable=True))
    op.add_column("workflows", sa.Column("budget_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflows", "budget_json")
    op.drop_column("workflows", "published_version_id")
