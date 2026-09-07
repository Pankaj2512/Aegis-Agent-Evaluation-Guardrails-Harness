"""Trust-layer foundations: run_spans nested-trace table + run tags/sessions.

Additive and reversible. Adds:
- run_spans (self-referential nested execution-trace tree)
- workflow_runs.session_id (indexed) + workflow_runs.tags_json

NodeResult/LlmCall are untouched (kept for back-compat); RunSpan is the new
trace-tree source. Downgrade drops the new table/columns.

Revision ID: 012_run_spans_tags_sessions
Revises: 011_workflow_templates
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_run_spans_tags_sessions"
down_revision = "011_workflow_templates"
branch_labels = None
depends_on = None

_TS_DEFAULT = sa.text("CURRENT_TIMESTAMP")


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    # run_spans table
    if "run_spans" not in _existing_tables():
        op.create_table(
            "run_spans",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("run_id", sa.UUID(), nullable=False),
            sa.Column("parent_span_id", sa.UUID(), nullable=True),
            sa.Column("node_id", sa.String(length=128), nullable=True),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="completed", nullable=False),
            sa.Column("offset_ms", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("attributes_json", sa.JSON(), nullable=True),
            sa.Column("tokens_json", sa.JSON(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=_TS_DEFAULT,
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_span_id"], ["run_spans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_run_spans_run_id", "run_spans", ["run_id"])
        op.create_index("ix_run_spans_run_parent", "run_spans", ["run_id", "parent_span_id"])

    # workflow_runs: session_id (indexed) + tags_json
    run_cols = _columns("workflow_runs") if "workflow_runs" in _existing_tables() else set()
    if "session_id" not in run_cols:
        op.add_column("workflow_runs", sa.Column("session_id", sa.String(length=128), nullable=True))
        op.create_index("ix_workflow_runs_session_id", "workflow_runs", ["session_id"])
    if "tags_json" not in run_cols:
        op.add_column("workflow_runs", sa.Column("tags_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    run_cols = _columns("workflow_runs") if "workflow_runs" in _existing_tables() else set()
    if "tags_json" in run_cols:
        op.drop_column("workflow_runs", "tags_json")
    if "session_id" in run_cols:
        op.drop_index("ix_workflow_runs_session_id", table_name="workflow_runs")
        op.drop_column("workflow_runs", "session_id")

    if "run_spans" in _existing_tables():
        op.drop_index("ix_run_spans_run_parent", table_name="run_spans")
        op.drop_index("ix_run_spans_run_id", table_name="run_spans")
        op.drop_table("run_spans")
