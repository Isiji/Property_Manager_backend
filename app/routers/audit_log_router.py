# app/routers/audit_log_router.py
from __future__ import annotations

from typing import List, Optional, Dict, Any, Set

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, role_required
from app.schemas.audit_log_schema import AuditLogOut
from app.crud import audit_log_crud

from app import models
from app.models.agency_models import PropertyAgentAssignment, PropertyExternalManagerAssignment

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _enrich(db: Session, rows: List[models.AuditLog]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # Avoid N+1 in a simple way
    prop_ids = [r.property_id for r in rows if r.property_id]
    props = {}
    if prop_ids:
        for p in db.query(models.Property).filter(models.Property.id.in_(prop_ids)).all():
            props[p.id] = p

    for r in rows:
        p = props.get(r.property_id) if r.property_id else None
        out.append({
            "id": r.id,
            "property_id": r.property_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "message": r.message,
            "actor_role": r.actor_role,
            "actor_id": r.actor_id,
            "created_at": r.created_at,
            "property_name": getattr(p, "name", None) if p else None,
            "property_code": getattr(p, "property_code", None) if p else None,
        })
    return out


@router.get(
    "/me",
    response_model=List[AuditLogOut],
    dependencies=[Depends(role_required(["admin", "landlord", "manager", "property_manager", "super_admin"]))],
)
def my_audit_logs(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None),
):
    role = (current or {}).get("role")
    sub = int((current or {}).get("sub", 0) or 0)

    # Admin: sees everything
    if role == "admin" or "super_admin":
        rows = audit_log_crud.list_logs(db, property_ids=None, limit=limit, q=q)
        return _enrich(db, rows)

    # Landlord: only properties they own
    if role == "landlord":
        prop_ids = [
            p.id for p in db.query(models.Property.id).filter(models.Property.landlord_id == sub).all()
        ]
        rows = audit_log_crud.list_logs(db, property_ids=prop_ids, limit=limit, q=q)
        return _enrich(db, rows)

    # Manager/Property_manager:
    # IMPORTANT: your manager JWT uses:
    #  - sub = staff_id
    #  - manager_id = org id
    manager_id = None
    try:
        manager_id = int((current or {}).get("manager_id") or 0) or None
    except Exception:
        manager_id = None

    staff_id = sub

    # A) org-managed
    q_org = db.query(models.Property.id).filter(models.Property.manager_id == manager_id) if manager_id else db.query(models.Property.id).filter(False)

    # B) staff assignments
    q_staff = (
        db.query(models.Property.id)
        .join(PropertyAgentAssignment, PropertyAgentAssignment.property_id == models.Property.id)
        .filter(
            PropertyAgentAssignment.assignee_user_id == staff_id,
            PropertyAgentAssignment.active == True,  # noqa
        )
    )

    # C) external manager assignment (org-level)
    q_ext = (
        db.query(models.Property.id)
        .join(PropertyExternalManagerAssignment, PropertyExternalManagerAssignment.property_id == models.Property.id)
        .filter(
            PropertyExternalManagerAssignment.agent_manager_id == manager_id,
            PropertyExternalManagerAssignment.active == True,  # noqa
        )
    ) if manager_id else db.query(models.Property.id).filter(False)

    ids: Set[int] = set([r[0] for r in q_org.all()] + [r[0] for r in q_staff.all()] + [r[0] for r in q_ext.all()])

    rows = audit_log_crud.list_logs(db, property_ids=list(ids), limit=limit, q=q)
    return _enrich(db, rows)