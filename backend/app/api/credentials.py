from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.schemas.credential import CredentialCreate, CredentialListItem, CredentialResponse
from app.services.credentials import (
    decrypt_credential_config,
    encrypt_credential_config,
    mask_credential_config,
)
from app.services.integrations import clear_pg_engine_for_url

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialListItem])
def list_credentials(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    rows = (
        db.query(models.Credential)
        .filter(models.Credential.user_id == user_id)
        .order_by(models.Credential.name.asc())
        .all()
    )
    return [
        CredentialListItem(
            id=row.id,
            name=row.name,
            type=row.type,
            config=mask_credential_config(row.type, row.config),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("", response_model=CredentialResponse)
def create_credential(
    payload: CredentialCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    existing = (
        db.query(models.Credential)
        .filter(models.Credential.user_id == user_id, models.Credential.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Credential '{payload.name}' already exists")

    row = models.Credential(
        user_id=user_id,
        name=payload.name,
        type=payload.type,
        config=encrypt_credential_config(payload.config),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CredentialResponse(
        id=row.id,
        name=row.name,
        type=row.type,
        config=mask_credential_config(row.type, row.config),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/{credential_id}")
def delete_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    row = (
        db.query(models.Credential)
        .filter(models.Credential.id == credential_id, models.Credential.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Credential not found")
    if row.type == "postgres":
        connection_url = decrypt_credential_config(row.config or {}).get("connection_url")
        if connection_url:
            clear_pg_engine_for_url(connection_url)
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": str(credential_id)}