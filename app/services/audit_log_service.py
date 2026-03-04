# app/services/audit_log_service.py
import json
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.schemas.audit_log_schema import AuditLogCreate
from app.crud import audit_log_crud


def log(
    db: Session,
    actor_role: str,
    actor_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    meta_json = None
    try:
        if meta is not None:
            meta_json = json.dumps(meta, ensure_ascii=False)
    except Exception:
        meta_json = None

    payload = AuditLogCreate(
        actor_role=actor_role,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        meta_json=meta_json,
        ip_address=ip,
        user_agent=user_agent,
    )
    return audit_log_crud.create_log(db, payload)