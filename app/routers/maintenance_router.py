from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

from .. import models
from app.schemas import maintenance_schema as schemas
from ..dependencies import get_db

router = APIRouter(prefix="/maintenance", tags=["Maintenance Requests"])

# -----------------------------
# Create a maintenance request
# -----------------------------
@router.post("/", response_model=schemas.MaintenanceRequestOut)
def create_request(payload: schemas.MaintenanceRequestCreate, db: Session = Depends(get_db)):
    mr = models.MaintenanceRequest(**payload.model_dump())
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return mr

# -----------------------------
# List requests with filters
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
    query = db.query(models.MaintenanceRequest)

    if tenant_id:
        query = query.filter(models.MaintenanceRequest.tenant_id == tenant_id)
    if unit_id:
        query = query.filter(models.MaintenanceRequest.unit_id == unit_id)
    if status_id:
        query = query.filter(models.MaintenanceRequest.status_id == status_id)
    if start_date:
        query = query.filter(models.MaintenanceRequest.created_at >= start_date)
    if end_date:
        query = query.filter(models.MaintenanceRequest.created_at <= end_date)

    return query.order_by(models.MaintenanceRequest.created_at.desc()).all()

# -----------------------------
# Update request
# -----------------------------
@router.put("/{mr_id}", response_model=schemas.MaintenanceRequestOut)
def update_request(mr_id: int, payload: schemas.MaintenanceRequestUpdate, db: Session = Depends(get_db)):
    mr = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(mr, key, value)

    db.commit()
    db.refresh(mr)
    return mr

# -----------------------------
# Delete request
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
# Reports: Monthly Breakdown
# -----------------------------
@router.get("/reports/monthly", tags=["Reports"])
def monthly_maintenance_report(
    db: Session = Depends(get_db),
    year: int = datetime.utcnow().year,
    unit_id: Optional[int] = None,
):
    """
    Returns the number of requests per month for a given year (optionally per unit).
    """
    query = db.query(
        func.extract("month", models.MaintenanceRequest.created_at).label("month"),
        func.count(models.MaintenanceRequest.id).label("request_count"),
    ).filter(func.extract("year", models.MaintenanceRequest.created_at) == year)

    if unit_id:
        query = query.filter(models.MaintenanceRequest.unit_id == unit_id)

    query = query.group_by("month").order_by("month").all()

    return [
        {"month": int(month), "request_count": request_count}
        for month, request_count in query
    ]


# -----------------------------
# Reports: Status Summary
# -----------------------------
@router.get("/reports/status-summary", tags=["Reports"])
def status_summary(
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    unit_id: Optional[int] = None,
):
    """
    Returns number of requests by status (open, in_progress, resolved, etc.)
    """
    query = db.query(
        models.MaintenanceStatus.name,
        func.count(models.MaintenanceRequest.id).label("count"),
    ).join(models.MaintenanceStatus)

    if unit_id:
        query = query.filter(models.MaintenanceRequest.unit_id == unit_id)
    if start_date:
        query = query.filter(models.MaintenanceRequest.created_at >= start_date)
    if end_date:
        query = query.filter(models.MaintenanceRequest.created_at <= end_date)

    query = query.group_by(models.MaintenanceStatus.name).all()

    return [{"status": status, "count": count} for status, count in query]


# -----------------------------
# Reports: Average Resolution Time
# -----------------------------
@router.get("/reports/average-resolution", tags=["Reports"])
def average_resolution_time(
    db: Session = Depends(get_db),
    unit_id: Optional[int] = None,
):
    """
    Calculates the average resolution time in days for resolved requests.
    Assumes status 'resolved' exists in MaintenanceStatus.
    """
    resolved_status = db.query(models.MaintenanceStatus).filter(
        models.MaintenanceStatus.name == "resolved"
    ).first()
    if not resolved_status:
        return {"message": "No 'resolved' status defined in system"}

    query = db.query(
        func.avg(func.julianday(models.MaintenanceRequest.updated_at) - func.julianday(models.MaintenanceRequest.created_at))
    ).filter(models.MaintenanceRequest.status_id == resolved_status.id)

    if unit_id:
        query = query.filter(models.MaintenanceRequest.unit_id == unit_id)

    avg_days = query.scalar()
    return {"average_resolution_days": round(avg_days, 2) if avg_days else None}
