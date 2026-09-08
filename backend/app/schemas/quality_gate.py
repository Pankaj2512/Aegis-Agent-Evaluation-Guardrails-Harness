"""Schemas for Aegis Quality Gate verification and pre-publish enforcement."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QualityCheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNED = "warned"
    SKIPPED = "skipped"


class QualityGateConfig(BaseModel):
    """Configuration rules for gating workflow versions before production publishing."""

    enabled: bool = Field(
        default=True,
        description="Whether quality gate enforcement is active for this workflow version.",
    )
    min_eval_score: float | None = Field(
        default=3.5,
        ge=1.0,
        le=5.0,
        description="Minimum acceptable average aggregate eval score (1-5 scale).",
    )
    min_pass_rate: float | None = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable proportion of runs where eval_passed is True.",
    )
    max_guardrail_block_rate: float | None = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Maximum allowed fraction of runs blocked by guardrails.",
    )
    max_p95_latency_ms: float | None = Field(
        default=15000.0,
        gt=0.0,
        description="Maximum allowed 95th percentile execution duration in milliseconds.",
    )
    block_on_regression: bool = Field(
        default=True,
        description="Block publishing if candidate score drops significantly vs the baseline published version.",
    )
    regression_tolerance: float = Field(
        default=0.30,
        ge=0.0,
        le=2.0,
        description="Allowed drop in eval aggregate score before flagging a regression blocker.",
    )
    require_eval_runs: bool = Field(
        default=False,
        description="Require at least min_runs_evaluated benchmark or test runs before publishing.",
    )
    min_runs_evaluated: int = Field(
        default=1,
        ge=1,
        description="Minimum number of evaluated runs required when require_eval_runs is enabled.",
    )


class QualityCheckItem(BaseModel):
    """Result of an individual check executed as part of the quality gate."""

    check_id: str
    name: str
    status: QualityCheckStatus
    metric_value: float | None = None
    threshold_value: float | None = None
    details: str
    remediation: str | None = None


class QualityGateReport(BaseModel):
    """Comprehensive evaluation report returned before publishing a workflow version."""

    workflow_id: UUID
    version_id: UUID
    version_number: int
    passed: bool
    can_publish: bool
    gate_enabled: bool
    summary: str
    checks: list[QualityCheckItem] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    candidate_metrics: dict[str, Any] = Field(default_factory=dict)
    baseline_metrics: dict[str, Any] | None = None


class PublishPayload(BaseModel):
    """Payload for publishing a workflow version with optional quality gate bypass."""

    version_id: UUID
    force: bool = Field(
        default=False,
        description="Whether to bypass failing quality gate checks (records an override in the audit log).",
    )
    override_reason: str | None = Field(
        default=None,
        description="Justification note required when force is True.",
    )

