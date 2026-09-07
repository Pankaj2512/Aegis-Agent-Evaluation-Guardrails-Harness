from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.data.templates import WORKFLOW_TEMPLATES
from app.db import models
from app.db.database import get_db
from app.schemas.template import TemplateCreate, TemplateItem, TemplateUseResponse
from app.services.eval_preset_service import list_all_presets
from app.services.graph_validation import GraphValidationError, validate_workflow_graph

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _builtin_items() -> list[TemplateItem]:
    return [
        TemplateItem(
            id=t["id"],
            name=t["name"],
            description=t.get("description", ""),
            graph_json=t["graph_json"],
            author=None,
            usage_count=0,
            created_at=None,
            builtin=True,
        )
        for t in WORKFLOW_TEMPLATES
    ]


def _persisted_item(row: models.WorkflowTemplate) -> TemplateItem:
    return TemplateItem(
        id=str(row.id),
        name=row.name,
        description=row.description or "",
        graph_json=row.graph_json,
        author=str(row.author) if row.author else None,
        usage_count=row.usage_count,
        created_at=row.created_at,
        builtin=False,
    )


@router.get("", response_model=list[TemplateItem])
def list_templates(
    db: Session = Depends(get_db),
    _user_id: UUID = Depends(get_current_user_id),
):
    """Return built-in templates and all persisted (user-published) templates.

    Built-ins report author=null, usage_count=0, builtin=true. Backward
    compatible with the existing frontend shape (fields added, none removed).
    """
    items = _builtin_items()
    persisted = (
        db.query(models.WorkflowTemplate)
        .order_by(models.WorkflowTemplate.created_at.desc())
        .all()
    )
    items.extend(_persisted_item(row) for row in persisted)
    return items


@router.post("", response_model=TemplateItem)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Snapshot a workflow's current graph into a persisted template."""
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == payload.workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    version = (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == payload.workflow_id)
        .order_by(models.WorkflowVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Workflow has no versions to snapshot")

    graph = version.graph_json or {}
    try:
        validate_workflow_graph(graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    template = models.WorkflowTemplate(
        name=payload.name,
        description=payload.description,
        graph_json=graph,
        author=user_id,
        usage_count=0,
        source_workflow_id=payload.workflow_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _persisted_item(template)


@router.post("/{template_id}/use", response_model=TemplateUseResponse)
def use_template(
    template_id: str,
    db: Session = Depends(get_db),
    _user_id: UUID = Depends(get_current_user_id),
):
    """Increment usage_count and return the template's graph for cloning.

    Works for both built-ins (usage is not persisted) and persisted templates.
    """
    # Built-in templates are matched by their string id.
    for t in WORKFLOW_TEMPLATES:
        if t["id"] == template_id:
            return TemplateUseResponse(
                id=t["id"],
                name=t["name"],
                graph_json=t["graph_json"],
                usage_count=0,
            )

    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Template not found")

    template = (
        db.query(models.WorkflowTemplate)
        .filter(models.WorkflowTemplate.id == template_uuid)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.usage_count = (template.usage_count or 0) + 1
    db.commit()
    db.refresh(template)
    return TemplateUseResponse(
        id=str(template.id),
        name=template.name,
        graph_json=template.graph_json,
        usage_count=template.usage_count,
    )


@router.get("/eval-presets")
def list_eval_presets(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return list_all_presets(db, user_id)
