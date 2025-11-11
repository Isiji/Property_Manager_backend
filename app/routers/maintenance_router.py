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

router = APIRouter(prefix="/maintenance", tags=["Maintenance Requests"])

# -----------------------------
# Status list (fixes 405/307)
# -----------------------------
@router.get("/status", response_model=List[schemas.MaintenanceStatusOut])
def list_statuses(db: Session = Depends(get_db)):
    return db.query(models.MaintenanceStatus).order_by(models.MaintenanceStatus.name.asc()).all()

# -----------------------------
# Create
# -----------------------------
@router.post("/", response_model=schemas.MaintenanceRequestOut)
def create_request(payload: schemas.MaintenanceRequestCreate, db: Session = Depends(get_db)):
    mr = models.MaintenanceRequest(**payload.model_dump())
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return mr

# -----------------------------
# List (filters)
# -----------------------------
@router.get("/", response_model=List[schemas.MaintenanceRequestOut])
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
@router.put("/{mr_id}", response_model=schemas.MaintenanceRequestOut)
def update_request(mr_id: int, payload: schemas.MaintenanceRequestUpdate, db: Session = Depends(get_db)):
    mr = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")

    before_status_id = mr.status_id
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(mr, k, v)
    mr.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(mr)

    # notify tenant if status changed
    if before_status_id != mr.status_id:
        status_obj = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.id == mr.status_id).first()
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
@router.delete("/{mr_id}")
def delete_request(mr_id: int, db: Session = Depends(get_db)):
    mr = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")
    db.delete(mr)
    db.commit()
    return {"message": "Maintenance request deleted successfully"}

# -----------------------------
# Reports: Monthly
# -----------------------------
@router.get("/reports/monthly", tags=["Reports"])
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
@router.get("/reports/status-summary", tags=["Reports"])
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
@router.get("/reports/average-resolution", tags=["Reports"])
def average_resolution_time(db: Session = Depends(get_db), unit_id: Optional[int] = None):
    resolved = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.name == "resolved").first()
    if not resolved:
        return {"average_resolution_days": None}

    # works on SQLite; for Postgres you can use AGE/EXTRACT(EPOCH…)
    avg_days = db.query(
        func.avg(func.julianday(models.MaintenanceRequest.updated_at) - func.julianday(models.MaintenanceRequest.created_at))
    ).filter(models.MaintenanceRequest.status_id == resolved.id)

    if unit_id:
        avg_days = avg_days.filter(models.MaintenanceRequest.unit_id == unit_id)

    v = avg_days.scalar()
    return {"average_resolution_days": round(v, 2) if v else None}

@router.get("/my")
def list_my_requests(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """
    Role-aware inbox:
    - landlord: all requests from units in properties you own
    - property_manager/manager: all requests from units in properties you manage
    - tenant: your own requests
    Returns enriched rows the frontend expects:
      id, description, status, created_at, updated_at,
      unit_id, unit_number, property_id, property_name
    """
    role = (current or {}).get("role")
    sub  = int((current or {}).get("sub", 0) or 0)
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
        # other roles get nothing for now
        return []

    rows = q.all()
    out = []
    for m in rows:
        unit = m.unit
        prop = unit.property if unit else None
        out.append({
            "id": m.id,
            "description": m.description,
            "status": getattr(m.status, "name", None),
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "unit_id": m.unit_id,
            "unit_number": getattr(unit, "number", None),
            "property_id": getattr(prop, "id", None),
            "property_name": getattr(prop, "name", None),
        })
    return out
