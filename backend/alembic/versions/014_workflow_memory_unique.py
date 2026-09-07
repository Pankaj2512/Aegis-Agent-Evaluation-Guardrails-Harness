"""Unique key on workflow_memory (workflow_id, namespace, key).

Prevents racy upserts from creating duplicate cells that later resolve to a
stale value. Dedupes existing duplicates (keeps the newest updated_at) before
creating the unique index.

Revision ID: 014_workflow_memory_unique
Revises: 013_alert_baseline_comparison
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014_workflow_memory_unique"
down_revision = "013_alert_baseline_comparison"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_tables() -> set[str]:
    return set(_inspector().get_table_names())


def _existing_indexes(table: str) -> set[str]:
    return {ix["name"] for ix in _inspector().get_indexes(table)}


def upgrade() -> None:
    if "workflow_memory" not in _existing_tables():
        return

    # Drop older duplicate rows, keeping the newest updated_at per key.
    # Works on both SQLite and Postgres via correlated subquery.
    op.execute(
        sa.text(
            """
            DELETE FROM workflow_memory
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY workflow_id, namespace, key
                               ORDER BY updated_at DESC
                           ) AS rn
                    FROM workflow_memory
                ) ranked
                WHERE rn = 1
            )
            """
        )
    )

    indexes = _existing_indexes("workflow_memory")
    if "uq_workflow_memory_wf_ns_key" not in indexes:
        op.create_index(
            "uq_workflow_memory_wf_ns_key",
            "workflow_memory",
            ["workflow_id", "namespace", "key"],
            unique=True,
        )


def downgrade() -> None:
    if "workflow_memory" not in _existing_tables():
        return
    indexes = _existing_indexes("workflow_memory")
    if "uq_workflow_memory_wf_ns_key" in indexes:
        op.drop_index("uq_workflow_memory_wf_ns_key", table_name="workflow_memory")
