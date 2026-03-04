# app/services/audit_service.py
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from app.schemas.audit_log_schema import AuditLogCreate
from app.crud import audit_log_crud


def log(
    db: Session,
    current_user: dict | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    message: str | None = None,
    property_id: Optional[int] = None,
):
    payload = AuditLogCreate(
        property_id=property_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
    )
    return audit_log_crud.create_log(db, payload, actor_user=current_user)