"""Dialect-aware UTC helpers for correct datetime comparisons.

Runs store timestamps via ``func.now()``. Under **Postgres** the columns are
``timestamptz`` (tz-aware); under **SQLite** (the documented dev default) the
same columns come back as **naive** UTC. A single Python "now" cannot be
compared correctly against both:

* Sending a *naive* datetime to a Postgres ``timestamptz`` comparison makes PG
  interpret the literal in the session ``TimeZone`` — off by the session offset
  when it is not UTC (audit P2-18).
* Sending a *tz-aware* datetime to compare against SQLite's naive strings
  mismatches lexically.

``to_db_utc`` / ``db_utcnow`` return the flavor the bound dialect compares
correctly against these columns: tz-aware UTC for Postgres, naive UTC for
SQLite.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session


def _dialect_name(db: Session) -> str:
    try:
        bind = db.get_bind()
    except Exception:  # noqa: BLE001 — best-effort; default to aware UTC
        return ""
    return bind.dialect.name if bind is not None else ""


def to_db_utc(db: Session, dt: datetime) -> datetime:
    """Coerce ``dt`` to the UTC flavor the bound dialect compares correctly.

    Postgres → tz-aware UTC (anchored regardless of session TimeZone);
    SQLite → naive UTC (matches ``func.now()`` storage).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if _dialect_name(db) == "sqlite":
        return dt.replace(tzinfo=None)
    return dt


def db_utcnow(db: Session) -> datetime:
    """`now` in UTC, in the flavor the bound dialect compares/stores correctly."""
    return to_db_utc(db, datetime.now(timezone.utc))
