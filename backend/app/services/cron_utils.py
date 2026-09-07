"""Cron expression helpers for schedule triggers."""

from __future__ import annotations

from datetime import datetime, timezone

from croniter import croniter


def cron_next_runs(cron_expr: str, count: int = 3, now: datetime | None = None) -> list[datetime]:
    moment = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    expr = cron_expr.strip()
    if not expr:
        return []
    itr = croniter(expr, moment)
    return [itr.get_next(datetime).replace(tzinfo=timezone.utc) for _ in range(max(1, count))]


def cron_is_valid(cron_expr: str) -> bool:
    expr = (cron_expr or "").strip()
    if not expr:
        return False
    try:
        croniter(expr)
        return True
    except (ValueError, KeyError):
        return False