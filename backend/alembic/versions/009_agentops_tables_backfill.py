"""Backfill AgentOps tables that were previously created by Base.metadata.create_all.

Migrations 001-008 never created these nine tables — they existed only because
``main.py`` called ``Base.metadata.create_all`` on startup. Now that Alembic is
the single source of schema truth (create_all removed), this migration creates
them idempotently so ``alembic upgrade head`` on a fresh database yields the
full schema.

Revision ID: 009_agentops_tables_backfill
Revises: 008_agentops_tables
"""

import sqlalchemy as sa
from alembic import op

revision = "009_agentops_tables_backfill"
down_revision = "008_agentops_tables"
branch_labels = None
depends_on = None

_TS_DEFAULT = sa.text("CURRENT_TIMESTAMP")

# Idempotency guard: on databases that were bootstrapped by the old create_all
# path these tables already exist. Skip creation for any that are present.
_TABLES = [
    "llm_calls",
    "datasets",
    "dataset_items",
    "experiments",
    "feedback",
    "guardrail_policies",
    "alert_rules",
    "alert_events",
    "audit_log",
]


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "llm_calls" not in existing:
        op.create_table(
            "llm_calls",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("run_id", sa.UUID(), nullable=False),
            sa.Column("node_id", sa.String(length=128), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("prompt_text", sa.Text(), nullable=True),
            sa.Column("completion_text", sa.Text(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("thinking_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])

    if "datasets" not in existing:
        op.create_table(
            "datasets",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("workflow_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_datasets_user_id", "datasets", ["user_id"])

    if "dataset_items" not in existing:
        op.create_table(
            "dataset_items",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("dataset_id", sa.UUID(), nullable=False),
            sa.Column("input_text", sa.Text(), nullable=False),
            sa.Column("expected_output", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "experiments" not in existing:
        op.create_table(
            "experiments",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("workflow_id", sa.UUID(), nullable=False),
            sa.Column("dataset_id", sa.UUID(), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False, server_default="batch"),
            sa.Column("version_id", sa.UUID(), nullable=False),
            sa.Column("baseline_version_id", sa.UUID(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_experiments_user_id", "experiments", ["user_id"])

    if "feedback" not in existing:
        op.create_table(
            "feedback",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("run_id", sa.UUID(), nullable=False),
            sa.Column("node_id", sa.String(length=128), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
        op.create_index("ix_feedback_run_id", "feedback", ["run_id"])

    if "guardrail_policies" not in existing:
        op.create_table(
            "guardrail_policies",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("rules_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_guardrail_policies_user_id", "guardrail_policies", ["user_id"])

    if "alert_rules" not in existing:
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("workflow_id", sa.UUID(), nullable=True),
            sa.Column("metric", sa.String(length=48), nullable=False),
            sa.Column("operator", sa.String(length=8), nullable=False, server_default="gt"),
            sa.Column("threshold", sa.Float(), nullable=False),
            sa.Column("window_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("channel_url", sa.String(length=512), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_alert_rules_user_id", "alert_rules", ["user_id"])

    if "alert_events" not in existing:
        op.create_table(
            "alert_events",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("rule_id", sa.UUID(), nullable=False),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("fired_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_alert_events_rule_id", "alert_events", ["rule_id"])

    if "audit_log" not in existing:
        op.create_table(
            "audit_log",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("entity_type", sa.String(length=48), nullable=False),
            sa.Column("entity_id", sa.String(length=64), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS_DEFAULT, nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_log_user_created", "audit_log", ["user_id", "created_at"])


def downgrade() -> None:
    existing = _existing_tables()
    for table in reversed(_TABLES):
        if table in existing:
            op.drop_table(table)
