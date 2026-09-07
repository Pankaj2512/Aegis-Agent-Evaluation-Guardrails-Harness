"""Add workflow_templates table (user-published templates with provenance).

Reversible: downgrade drops the table. New table only — no data migration.

Revision ID: 011_workflow_templates
Revises: 010_encrypt_credential_secrets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "011_workflow_templates"
down_revision = "010_encrypt_credential_secrets"
branch_labels = None
depends_on = None

_TS_DEFAULT = sa.text("CURRENT_TIMESTAMP")


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    if "workflow_templates" in _existing_tables():
        return
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("author", sa.Uuid(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_workflow_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_TS_DEFAULT,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_templates_author", "workflow_templates", ["author"])


def downgrade() -> None:
    if "workflow_templates" not in _existing_tables():
        return
    op.drop_index("ix_workflow_templates_author", table_name="workflow_templates")
    op.drop_table("workflow_templates")
