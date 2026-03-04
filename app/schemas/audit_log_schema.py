# app/schemas/audit_log_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogCreate(BaseModel):
    property_id: Optional[int] = None

    action: str
    entity_type: str
    entity_id: Optional[int] = None
    message: Optional[str] = None

    actor_role: Optional[str] = None
    actor_id: Optional[int] = None


class AuditLogOut(BaseModel):
    id: int
    property_id: Optional[int] = None

    action: str
    entity_type: str
    entity_id: Optional[int] = None
    message: Optional[str] = None

    actor_role: Optional[str] = None
    actor_id: Optional[int] = None

    created_at: datetime

    # small property summary for UI
    property_name: Optional[str] = None
    property_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)