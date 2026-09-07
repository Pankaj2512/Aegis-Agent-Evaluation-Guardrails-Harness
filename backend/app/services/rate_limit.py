"""In-memory, per-endpoint rate limiting keyed by user (falling back to key/IP).

Generalizes the old flat ``rate_limit_per_minute`` into a path/method → limit
map so hot mutating endpoints (POST /api/runs, /v1/.../invoke) can be throttled
independently of cheap reads. The sliding-window + endpoint-map approach mirrors
``services/assist.py::check_assist_rate_limit`` (_ENDPOINT_LIMITS).

IMPORTANT: buckets live in this process's memory, so limits are enforced
per-instance. A multi-instance deployment needs a shared store (Redis) for
global limits — that is intentionally out of scope here.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from app.auth.deps import _resolve_api_token, user_id_from_api_key
from app.config import settings

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)
_last_prune = 0.0

# Endpoint tier → config setting name holding the per-minute limit. Each tier is
# matched by (method, compiled-path-regex). The first matching rule wins; paths
# with no rule fall back to the flat ``rate_limit_per_minute`` tier.
_UUID = r"[^/]+"

# (method, path_regex, setting_name)
_ENDPOINT_RULES: list[tuple[str, re.Pattern[str], str]] = [
    # High-cost run creation.
    ("POST", re.compile(rf"^/api/runs/?$"), "rate_limit_runs_create_per_minute"),
    # Medium: stable public invoke API (workflow-as-API).
    ("POST", re.compile(rf"^/v1/workflows/{_UUID}/invoke/?$"), "rate_limit_invoke_per_minute"),
    ("POST", re.compile(rf"^/v1/ingest/runs/?$"), "rate_limit_invoke_per_minute"),
]

# GET/HEAD reads on the API surface get a generous read tier.
_READ_METHODS = frozenset({"GET", "HEAD"})


def _limit_setting_for(method: str, path: str) -> str:
    for rule_method, pattern, setting_name in _ENDPOINT_RULES:
        if method == rule_method and pattern.match(path):
            return setting_name
    if method in _READ_METHODS and path.startswith("/api/"):
        return "rate_limit_read_per_minute"
    return "rate_limit_per_minute"


def rate_limited_path(path: str) -> bool:
    """Which paths the middleware should submit to the limiter."""
    return path.startswith("/api/") or path.startswith("/v1/")


def _client_key(request: Request) -> str:
    # Prefer the authenticated user so limits track the caller, not the transport.
    token = _resolve_api_token(
        request.headers.get("authorization"),
        request.headers.get("X-Aegis-API-Key"),
        request.query_params.get("api_key"),
    )
    if token:
        try:
            return f"user:{user_id_from_api_key(token)}"
        except Exception:  # noqa: BLE001 — malformed token, fall back to raw key
            return f"key:{token}"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    if request.client:
        return f"ip:{request.client.host}"
    return "ip:unknown"


def _prune_stale_buckets(now: float, window_seconds: float) -> None:
    global _last_prune
    if now - _last_prune < window_seconds:
        return
    _last_prune = now
    stale_keys = [
        key
        for key, timestamps in _buckets.items()
        if not any(now - ts < window_seconds for ts in timestamps)
    ]
    for key in stale_keys:
        _buckets.pop(key, None)


def check_rate_limit(request: Request) -> None:
    if not settings.auth_enabled:
        return

    setting_name = _limit_setting_for(request.method, request.url.path)
    limit = max(1, int(getattr(settings, setting_name, None) or settings.rate_limit_per_minute or 120))
    window_seconds = 60.0
    now = time.monotonic()
    # Bucket per (client, tier) so a burst of reads can't starve the write tier
    # and vice versa.
    key = f"{_client_key(request)}|{setting_name}"

    with _lock:
        _prune_stale_buckets(now, window_seconds)
        recent = [ts for ts in _buckets[key] if now - ts < window_seconds]
        _buckets[key] = recent
        if len(recent) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests per minute)",
            )
        recent.append(now)
        _buckets[key] = recent
