"""Anomaly alerting: baseline-relative comparison on alert rules.

Additive and reversible. Adds to alert_rules:
- comparison (absolute | baseline) — default "absolute" preserves today's behavior
- baseline_window_minutes — trailing window the current metric is compared against
  when comparison == "baseline"

Percentile metrics (latency_p95/p99) reuse the existing metric column — no
schema change needed for those.

Revision ID: 013_alert_baseline_comparison
Revises: 012_run_spans_tags_sessions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_alert_baseline_comparison"
down_revision = "012_run_spans_tags_sessions"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    if "alert_rules" not in _existing_tables():
        return
    cols = _columns("alert_rules")
    if "comparison" not in cols:
        op.add_column(
            "alert_rules",
            sa.Column("comparison", sa.String(length=16), server_default="absolute", nullable=False),
        )
    if "baseline_window_minutes" not in cols:
        op.add_column(
            "alert_rules", sa.Column("baseline_window_minutes", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    if "alert_rules" not in _existing_tables():
        return
    cols = _columns("alert_rules")
    if "baseline_window_minutes" in cols:
        op.drop_column("alert_rules", "baseline_window_minutes")
    if "comparison" in cols:
        op.drop_column("alert_rules", "comparison")
