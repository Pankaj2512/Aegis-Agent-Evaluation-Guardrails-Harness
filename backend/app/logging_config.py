from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "workflow_id", "node_id", "user_id", "event", "trace_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_context(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    run_id: str | None = None,
    workflow_id: str | None = None,
    node_id: str | None = None,
    user_id: str | None = None,
    event: str | None = None,
    trace_id: str | None = None,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "run_id": run_id,
            "workflow_id": workflow_id,
            "node_id": node_id,
            "user_id": user_id,
            "event": event,
            "trace_id": trace_id,
        },
    )