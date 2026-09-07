"""Unit tests for MVP2 infra: migration gate, tiered rate limits, crypto, call resilience."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services import rate_limit
from app.services.startup import (
    MigrationsBehindError,
    check_migrations_current,
)


# ---------------------------------------------------------------------------
# Item 1: startup migration gate
# ---------------------------------------------------------------------------


def test_migration_gate_current_returns_true():
    # The test DB is stamped at head by conftest.
    assert check_migrations_current(strict=True) is True


def test_migration_gate_behind_raises(monkeypatch):
    monkeypatch.setattr(
        "app.services.startup._current_db_revisions", lambda: {"008_agentops_tables"}
    )
    monkeypatch.setattr(
        "app.services.startup._alembic_head_revisions", lambda: {"999_head"}
    )
    assert check_migrations_current(strict=False) is False
    with pytest.raises(MigrationsBehindError):
        check_migrations_current(strict=True)


# ---------------------------------------------------------------------------
# Item 3: tiered, per-user rate limits
# ---------------------------------------------------------------------------


def test_rate_limit_tier_resolution():
    assert rate_limit._limit_setting_for("POST", "/api/runs") == "rate_limit_runs_create_per_minute"
    assert (
        rate_limit._limit_setting_for("POST", "/v1/workflows/abc-123/invoke")
        == "rate_limit_invoke_per_minute"
    )
    assert rate_limit._limit_setting_for("GET", "/api/runs") == "rate_limit_read_per_minute"
    assert rate_limit._limit_setting_for("POST", "/api/workflows") == "rate_limit_per_minute"


def test_rate_limited_path():
    assert rate_limit.rate_limited_path("/api/runs") is True
    assert rate_limit.rate_limited_path("/v1/workflows/x/invoke") is True
    assert rate_limit.rate_limited_path("/health") is False


def _fake_request(method: str, path: str, api_key: str = "testkey"):
    req = MagicMock()
    req.method = method
    req.url.path = path

    class Headers(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    req.headers = Headers({"X-Aegis-API-Key": api_key})
    req.query_params = {}
    req.client.host = "1.2.3.4"
    return req


def test_rate_limit_enforces_tier_and_keys_per_user(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_enabled", True)
    monkeypatch.setattr("app.config.settings.aegis_api_key", "testkey")
    monkeypatch.setattr("app.config.settings.rate_limit_runs_create_per_minute", 5)
    rate_limit._buckets.clear()

    from fastapi import HTTPException

    # 5 allowed, 6th rejected — for the runs-create tier.
    for _ in range(5):
        rate_limit.check_rate_limit(_fake_request("POST", "/api/runs"))
    with pytest.raises(HTTPException) as exc:
        rate_limit.check_rate_limit(_fake_request("POST", "/api/runs"))
    assert exc.value.status_code == 429

    # A different tier (reads) for the same user is unaffected.
    rate_limit.check_rate_limit(_fake_request("GET", "/api/runs"))


def test_rate_limit_disabled_when_auth_off(monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_enabled", False)
    rate_limit._buckets.clear()
    for _ in range(1000):
        rate_limit.check_rate_limit(_fake_request("POST", "/api/runs"))  # never raises


# ---------------------------------------------------------------------------
# Item 4: bounded per-call timeout + retry injection
# ---------------------------------------------------------------------------


def test_apply_call_resilience_sets_bounded_timeout_and_retries(monkeypatch):
    monkeypatch.setattr("app.config.settings.node_llm_timeout_seconds", 60)
    monkeypatch.setattr("app.config.settings.node_llm_max_retries", 2)

    from types import SimpleNamespace

    from google.genai import types

    from app.services.token_tracker import _apply_call_resilience

    cfg = types.GenerateContentConfig()
    _apply_call_resilience(SimpleNamespace(config=cfg))

    ho = cfg.http_options
    # 60s budget / 3 attempts = 20s per attempt (ms).
    assert ho.timeout == 20_000
    assert ho.retry_options.attempts == 3
    assert ho.retry_options.exp_base == 2.0
    # Total worst case stays bounded by the per-call budget.
    assert ho.retry_options.max_delay <= 20


def test_apply_call_resilience_no_retries_when_disabled(monkeypatch):
    monkeypatch.setattr("app.config.settings.node_llm_max_retries", 0)

    from types import SimpleNamespace

    from google.genai import types

    from app.services.token_tracker import _apply_call_resilience

    cfg = types.GenerateContentConfig()
    _apply_call_resilience(SimpleNamespace(config=cfg))
    assert cfg.http_options.timeout is not None
    assert cfg.http_options.retry_options is None
