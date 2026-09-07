"""Release 2.5: user_id, webhook_url, and supporting tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_USER = "00000000-0000-0000-0000-000000000001"
_TS_DEFAULT = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("user_id", sa.UUID(), nullable=False, server_default=DEFAULT_USER),
    )
    op.add_column("workflows", sa.Column("webhook_url", sa.String(length=512), nullable=True))
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])

    op.create_table(
        "workflow_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_memory_workflow_id", "workflow_memory", ["workflow_id"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_workflow_id", "knowledge_documents", ["workflow_id"])

    op.create_table(
        "workflow_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(), nullable=False),
        sa.Column("cron_expr", sa.String(length=128), nullable=False),
        sa.Column("trigger_node_id", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cron_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_index("ix_workflow_schedules_workflow_id", "workflow_schedules", ["workflow_id"])

    op.create_table(
        "evaluation_presets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("criteria", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("score_weights", sa.JSON(), nullable=True),
        sa.Column("eval_type", sa.String(length=32), nullable=False, server_default="llm"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_presets_user_id", "evaluation_presets", ["user_id"])

    op.create_table(
        "credentials",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_TS_DEFAULT),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_credentials_user_id", table_name="credentials")
    op.drop_table("credentials")
    op.drop_index("ix_evaluation_presets_user_id", table_name="evaluation_presets")
    op.drop_table("evaluation_presets")
    op.drop_index("ix_workflow_schedules_workflow_id", table_name="workflow_schedules")
    op.drop_table("workflow_schedules")
    op.drop_index("ix_knowledge_documents_workflow_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_workflow_memory_workflow_id", table_name="workflow_memory")
    op.drop_table("workflow_memory")
    op.drop_index("ix_workflows_user_id", table_name="workflows")
    op.drop_column("workflows", "webhook_url")
    op.drop_column("workflows", "user_id")