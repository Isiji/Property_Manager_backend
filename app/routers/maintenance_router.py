from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

from app.dependencies import get_db, get_current_user
from app import models
from app.schemas import maintenance_schema as schemas
from app.schemas.notification_schema import NotificationCreate
from app.services import notification_service

# NOTE:
# We keep prefix="" so we can support BOTH:
#   /maintenance/...
# and
#   /tenants/me/maintenance
router = APIRouter(tags=["Maintenance Requests"])


def _normalize_role(role: Optional[str]) -> str:
    return (role or "").strip().lower()


def _pick_default_status_id(db: Session) -> Optional[int]:
    # Try "open" first, then the first available status row
    open_status = (
        db.query(models.MaintenanceStatus)
        .filter(func.lower(models.MaintenanceStatus.name) == "open")
        .first()
    )
    if open_status:
        return open_status.id

    first_status = (
        db.query(models.MaintenanceStatus)
        .order_by(models.MaintenanceStatus.id.asc())
        .first()
    )
    return first_status.id if first_status else None


def _build_maintenance_row(db: Session, mr: models.MaintenanceRequest) -> dict:
    status_obj = getattr(mr, "status", None)
    unit = getattr(mr, "unit", None)
    prop = unit.property if unit else None

    return {
        "id": mr.id,
        "tenant_id": mr.tenant_id,
        "lease_id": getattr(mr, "lease_id", None),
        "unit_id": mr.unit_id,
        "description": mr.description,
        "status_id": mr.status_id,
        "status": getattr(status_obj, "name", None),
        "created_at": mr.created_at.isoformat() if mr.created_at else None,
        "updated_at": mr.updated_at.isoformat() if mr.updated_at else None,
        "unit_number": getattr(unit, "number", None),
        "property_id": getattr(prop, "id", None),
        "property_name": getattr(prop, "name", None),
    }


def _notify_relevant_people_for_maintenance(
    db: Session,
    *,
    mr: models.MaintenanceRequest,
    tenant: Optional[models.Tenant],
    unit: Optional[models.Unit],
    prop: Optional[models.Property],
):
    tenant_name = getattr(tenant, "name", None) or "Tenant"
    unit_label = getattr(unit, "number", None) or f"Unit {mr.unit_id}"
    property_name = getattr(prop, "name", None) or "Property"
    title = "New maintenance request"
    message = f"{tenant_name} reported: {mr.description} ({property_name} • Unit {unit_label})"

    # Notify landlord
    if prop and getattr(prop, "landlord_id", None):
        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=prop.landlord_id,
                user_type="landlord",
                title=title,
                message=message,
                channel="inapp",
            ),
        )

    # Notify manager if assigned
    if prop and getattr(prop, "manager_id", None):
        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=prop.manager_id,
                user_type="manager",
                title=title,
                message=message,
                channel="inapp",
            ),
        )

    # Notify tenant as confirmation
    if tenant:
        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=tenant.id,
                user_type="tenant",
                title="Maintenance request submitted",
                message=f"Your request has been submitted for {property_name} • Unit {unit_label}",
                channel="inapp",
            ),
        )


# -----------------------------
# Status list
# -----------------------------
@router.get("/maintenance/status", response_model=List[schemas.MaintenanceStatusOut])
def list_statuses(db: Session = Depends(get_db)):
    return (
        db.query(models.MaintenanceStatus)
        .order_by(models.MaintenanceStatus.name.asc())
        .all()
    )


# -----------------------------
# Create (generic/admin/internal)
# -----------------------------
@router.post("/maintenance/", response_model=schemas.MaintenanceRequestOut)
def create_request(
    payload: schemas.MaintenanceRequestCreate,
    db: Session = Depends(get_db),
):
    mr = models.MaintenanceRequest(**payload.model_dump())
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return mr


# -----------------------------
# Tenant self-create
# EXACT path frontend is using:
# POST /tenants/me/maintenance
# -----------------------------
@router.post("/tenants/me/maintenance")
def create_my_maintenance(
    payload_in: dict,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = _normalize_role(current.get("role"))
    sub = int((current or {}).get("sub", 0) or 0)

    if role != "tenant" or not sub:
        raise HTTPException(status_code=403, detail="Tenant access only")

    description = (payload_in.get("description") or "").strip()
    lease_id_raw = payload_in.get("lease_id")

    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == sub).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    lease = None
    if lease_id_raw is not None:
        try:
            lease_id = int(lease_id_raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid lease_id")

        lease = (
            db.query(models.Lease)
            .options(
                joinedload(models.Lease.unit).joinedload(models.Unit.property)
            )
            .filter(
                models.Lease.id == lease_id,
                models.Lease.tenant_id == sub,
            )
            .first()
        )
    else:
        lease = (
            db.query(models.Lease)
            .options(
                joinedload(models.Lease.unit).joinedload(models.Unit.property)
            )
            .filter(
                models.Lease.tenant_id == sub,
                models.Lease.active == 1,
            )
            .order_by(models.Lease.id.desc())
            .first()
        )

    if not lease:
        raise HTTPException(status_code=404, detail="No active lease found")

    status_id = _pick_default_status_id(db)

    mr = models.MaintenanceRequest(
        tenant_id=sub,
        lease_id=lease.id,
        unit_id=lease.unit_id,
        description=description,
        status_id=status_id,
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)

    unit = getattr(lease, "unit", None)
    prop = unit.property if unit else None

    try:
        _notify_relevant_people_for_maintenance(
            db,
            mr=mr,
            tenant=tenant,
            unit=unit,
            prop=prop,
        )
    except Exception:
        # Notification failure should not fail the request itself
        pass

    mr = (
        db.query(models.MaintenanceRequest)
        .options(
            joinedload(models.MaintenanceRequest.status),
            joinedload(models.MaintenanceRequest.unit).joinedload(models.Unit.property),
        )
        .filter(models.MaintenanceRequest.id == mr.id)
        .first()
    )

    return {
        "ok": True,
        "message": "Maintenance request submitted",
        "request": _build_maintenance_row(db, mr),
    }


# -----------------------------
# List (filters)
# -----------------------------
@router.get("/maintenance/", response_model=List[schemas.MaintenanceRequestOut])
def list_requests(
    db: Session = Depends(get_db),
    tenant_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    status_id: Optional[int] = None,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    q = db.query(models.MaintenanceRequest)

    if tenant_id:
        q = q.filter(models.MaintenanceRequest.tenant_id == tenant_id)
    if unit_id:
        q = q.filter(models.MaintenanceRequest.unit_id == unit_id)
    if status_id:
        q = q.filter(models.MaintenanceRequest.status_id == status_id)
    if start_date:
        q = q.filter(models.MaintenanceRequest.created_at >= start_date)
    if end_date:
        q = q.filter(models.MaintenanceRequest.created_at <= end_date)

    return q.order_by(models.MaintenanceRequest.created_at.desc().nullslast()).all()


# -----------------------------
# Update (+ notify tenant on status change)
# -----------------------------
@router.put("/maintenance/{mr_id}", response_model=schemas.MaintenanceRequestOut)
def update_request(
    mr_id: int,
    payload: schemas.MaintenanceRequestUpdate,
    db: Session = Depends(get_db),
):
    mr = (
        db.query(models.MaintenanceRequest)
        .filter(models.MaintenanceRequest.id == mr_id)
        .first()
    )
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")

    before_status_id = mr.status_id
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(mr, k, v)
    mr.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(mr)

    if before_status_id != mr.status_id:
        status_obj = (
            db.query(models.MaintenanceStatus)
            .filter(models.MaintenanceStatus.id == mr.status_id)
            .first()
        )
        status_name = getattr(status_obj, "name", "updated")
        unit = db.query(models.Unit).filter(models.Unit.id == mr.unit_id).first()
        unit_label = getattr(unit, "number", f"Unit {mr.unit_id}")

        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=mr.tenant_id,
                user_type="tenant",
                title="Maintenance update",
                message=f"{unit_label}: status changed to {status_name}",
                channel="inapp",
            ),
        )

    return mr


# -----------------------------
# Delete
# -----------------------------
@router.delete("/maintenance/{mr_id}")
def delete_request(mr_id: int, db: Session = Depends(get_db)):
    mr = (
        db.query(models.MaintenanceRequest)
        .filter(models.MaintenanceRequest.id == mr_id)
        .first()
    )
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")
    db.delete(mr)
    db.commit()
    return {"message": "Maintenance request deleted successfully"}


# -----------------------------
# Reports: Monthly
# -----------------------------
@router.get("/maintenance/reports/monthly", tags=["Reports"])
def monthly_maintenance_report(
    db: Session = Depends(get_db),
    year: int = datetime.utcnow().year,
    unit_id: Optional[int] = None,
):
    q = db.query(
        func.extract("month", models.MaintenanceRequest.created_at).label("month"),
        func.count(models.MaintenanceRequest.id).label("request_count"),
    ).filter(func.extract("year", models.MaintenanceRequest.created_at) == year)

    if unit_id:
        q = q.filter(models.MaintenanceRequest.unit_id == unit_id)

    rows = q.group_by("month").order_by("month").all()
    return [{"month": int(m), "request_count": c} for m, c in rows]


# -----------------------------
# Reports: Status summary
# -----------------------------
@router.get("/maintenance/reports/status-summary", tags=["Reports"])
def status_summary(
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    unit_id: Optional[int] = None,
):
    q = db.query(
        models.MaintenanceStatus.name,
        func.count(models.MaintenanceRequest.id).label("count"),
    ).join(models.MaintenanceStatus)

    if unit_id:
        q = q.filter(models.MaintenanceRequest.unit_id == unit_id)
    if start_date:
        q = q.filter(models.MaintenanceRequest.created_at >= start_date)
    if end_date:
        q = q.filter(models.MaintenanceRequest.created_at <= end_date)

    rows = q.group_by(models.MaintenanceStatus.name).all()
    return [{"status": s, "count": c} for s, c in rows]


# -----------------------------
# Reports: Avg resolution (days)
# -----------------------------
@router.get("/maintenance/reports/average-resolution", tags=["Reports"])
def average_resolution_time(
    db: Session = Depends(get_db),
    unit_id: Optional[int] = None,
):
    resolved = (
        db.query(models.MaintenanceStatus)
        .filter(models.MaintenanceStatus.name == "resolved")
        .first()
    )
    if not resolved:
        return {"average_resolution_days": None}

    avg_days = db.query(
        func.avg(
            func.julianday(models.MaintenanceRequest.updated_at)
            - func.julianday(models.MaintenanceRequest.created_at)
        )
    ).filter(models.MaintenanceRequest.status_id == resolved.id)

    if unit_id:
        avg_days = avg_days.filter(models.MaintenanceRequest.unit_id == unit_id)

    v = avg_days.scalar()
    return {"average_resolution_days": round(v, 2) if v else None}


@router.get("/maintenance/my")
def list_my_requests(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = _normalize_role((current or {}).get("role"))
    sub = int((current or {}).get("sub", 0) or 0)
    if not role or not sub:
        raise HTTPException(status_code=401, detail="Invalid token")

    q = (
        db.query(models.MaintenanceRequest)
        .join(models.Unit, models.Unit.id == models.MaintenanceRequest.unit_id)
        .join(models.Property, models.Property.id == models.Unit.property_id)
        .options(
            joinedload(models.MaintenanceRequest.status),
            joinedload(models.MaintenanceRequest.unit).joinedload(models.Unit.property),
        )
        .order_by(models.MaintenanceRequest.created_at.desc().nullslast())
    )

    if role == "landlord":
        q = q.filter(models.Property.landlord_id == sub)
    elif role in ("property_manager", "manager"):
        q = q.filter(models.Property.manager_id == sub)
    elif role == "tenant":
        q = q.filter(models.MaintenanceRequest.tenant_id == sub)
    else:
        return []

    rows = q.all()
    return [_build_maintenance_row(db, m) for m in rows]