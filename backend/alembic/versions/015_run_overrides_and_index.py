"""Persist authoring overrides on runs + reconcile run index drift.

Adds ``workflow_runs.authoring_overrides_json`` so the worker process re-applies
pin/run-from-here overrides (they were previously kept only in the API process's
in-memory registry and silently dropped in worker mode — P2-1).

Also creates ``ix_workflow_runs_status_created_at`` which the ORM model declared
but no migration ever created — closing the model<->migration drift (P2-14).

Revision ID: 015_run_overrides_and_index
Revises: 014_workflow_memory_unique
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.models import JSONType

revision = "015_run_overrides_and_index"
down_revision = "014_workflow_memory_unique"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {ix["name"] for ix in _inspector().get_indexes(table)}


def upgrade() -> None:
    if "authoring_overrides_json" not in _columns("workflow_runs"):
        op.add_column(
            "workflow_runs",
            sa.Column("authoring_overrides_json", JSONType(), nullable=True),
        )
    if "ix_workflow_runs_status_created_at" not in _indexes("workflow_runs"):
        op.create_index(
            "ix_workflow_runs_status_created_at",
            "workflow_runs",
            ["status", "created_at"],
        )


def downgrade() -> None:
    if "ix_workflow_runs_status_created_at" in _indexes("workflow_runs"):
        op.drop_index("ix_workflow_runs_status_created_at", table_name="workflow_runs")
    if "authoring_overrides_json" in _columns("workflow_runs"):
        op.drop_column("workflow_runs", "authoring_overrides_json")
