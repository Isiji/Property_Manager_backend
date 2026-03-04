# app/crud/audit_log_crud.py
from __future__ import annotations

from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.schemas.audit_log_schema import AuditLogCreate


def create_log(db: Session, payload: AuditLogCreate, actor_user: dict | None = None) -> models.AuditLog:
    data = payload.model_dump()

    # Fill actor info from token if missing
    if actor_user:
        data["actor_role"] = data.get("actor_role") or actor_user.get("role")
        try:
            data["actor_id"] = data.get("actor_id") or int(actor_user.get("sub") or 0) or None
        except Exception:
            data["actor_id"] = data.get("actor_id") or None

    log = models.AuditLog(
        property_id=data.get("property_id"),
        action=(data.get("action") or "").strip(),
        entity_type=(data.get("entity_type") or "").strip(),
        entity_id=data.get("entity_id"),
        message=data.get("message"),
        actor_role=data.get("actor_role"),
        actor_id=data.get("actor_id"),
    )

    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(
    db: Session,
    property_ids: Optional[List[int]] = None,
    limit: int = 50,
    q: Optional[str] = None,
) -> List[models.AuditLog]:
    query = db.query(models.AuditLog)

    if property_ids is not None:
        if not property_ids:
            return []
        query = query.filter(models.AuditLog.property_id.in_(property_ids))

    if q:
        s = f"%{q.strip()}%"
        query = query.filter(or_(
            models.AuditLog.action.ilike(s),
            models.AuditLog.entity_type.ilike(s),
            models.AuditLog.message.ilike(s),
        ))

    return query.order_by(models.AuditLog.created_at.desc()).limit(limit).all()