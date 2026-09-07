"""Cross-run workflow memory (Lyzr Cognis-style persistence)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models


def namespace_to_dict(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    memory: dict[str, dict[str, str]] = {}
    for row in rows:
        ns = str(row.get("namespace") or "default")
        key = str(row.get("key") or "")
        if not key:
            continue
        memory.setdefault(ns, {})[key] = str(row.get("value") or "")
    return memory


def merge_memory_into_context(
    context: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    persisted = namespace_to_dict(rows)
    current = context.setdefault("memory", {})
    if not isinstance(current, dict):
        current = {}
        context["memory"] = current
    for ns, bucket in persisted.items():
        if not isinstance(bucket, dict):
            continue
        existing = current.setdefault(ns, {})
        if isinstance(existing, dict):
            existing.update(bucket)
        else:
            current[ns] = dict(bucket)


def load_workflow_memory(db: Session, workflow_id: UUID) -> list[dict[str, str]]:
    rows = (
        db.query(models.WorkflowMemory)
        .filter(models.WorkflowMemory.workflow_id == workflow_id)
        .order_by(models.WorkflowMemory.updated_at.desc())
        .all()
    )
    return [
        {
            "namespace": row.namespace,
            "key": row.key,
            "value": row.value,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def upsert_memory_entry(
    db: Session,
    workflow_id: UUID,
    namespace: str,
    key: str,
    value: str,
    *,
    commit: bool = True,
) -> None:
    """Upsert a single memory cell; serialized to avoid duplicate rows.

    Prefer the unique (workflow_id, namespace, key) index when present; fall back
    to SELECT FOR UPDATE + delete-stale-duplicates so concurrent writers cannot
    leave multiple rows that later resolve to a stale value.
    """
    from sqlalchemy.exc import IntegrityError

    ns = (namespace or "default").strip() or "default"
    rows = (
        db.query(models.WorkflowMemory)
        .filter(
            models.WorkflowMemory.workflow_id == workflow_id,
            models.WorkflowMemory.namespace == ns,
            models.WorkflowMemory.key == key,
        )
        .with_for_update()
        .order_by(models.WorkflowMemory.updated_at.desc())
        .all()
    )
    if rows:
        primary = rows[0]
        primary.value = value
        # Collapse any historical duplicates created before the unique index.
        for stale in rows[1:]:
            db.delete(stale)
    else:
        try:
            with db.begin_nested():
                db.add(
                    models.WorkflowMemory(
                        workflow_id=workflow_id,
                        namespace=ns,
                        key=key,
                        value=value,
                    )
                )
                db.flush()
        except IntegrityError:
            row = (
                db.query(models.WorkflowMemory)
                .filter(
                    models.WorkflowMemory.workflow_id == workflow_id,
                    models.WorkflowMemory.namespace == ns,
                    models.WorkflowMemory.key == key,
                )
                .with_for_update()
                .first()
            )
            if row is None:
                raise
            row.value = value
    if commit:
        db.commit()


def queue_memory_write(
    context_ref: dict[str, Any],
    workflow_id: UUID,
    namespace: str,
    key: str,
    value: str,
) -> None:
    pending = context_ref.setdefault("_memory_pending_writes", [])
    pending.append(
        {
            "workflow_id": str(workflow_id),
            "namespace": namespace,
            "key": key,
            "value": value,
        }
    )


def flush_memory_writes(db: Session, context_ref: dict[str, Any]) -> int:
    pending = context_ref.pop("_memory_pending_writes", [])
    if not pending:
        return 0
    for item in pending:
        upsert_memory_entry(
            db,
            UUID(str(item["workflow_id"])),
            str(item["namespace"]),
            str(item["key"]),
            str(item["value"]),
            commit=False,
        )
    db.commit()
    return len(pending)


def clear_workflow_memory(db: Session, workflow_id: UUID, namespace: str | None = None) -> int:
    query = db.query(models.WorkflowMemory).filter(models.WorkflowMemory.workflow_id == workflow_id)
    if namespace:
        query = query.filter(models.WorkflowMemory.namespace == namespace.strip())
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return count