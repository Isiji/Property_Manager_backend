from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .. import models
from ..schemas import maintenance as schemas
from ..dependencies import get_db

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# ==============================
# Maintenance Status CRUD
# ==============================

@router.post("/status/", response_model=schemas.MaintenanceStatusOut)
def create_status(payload: schemas.MaintenanceStatusCreate, db: Session = Depends(get_db)):
    existing = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Status already exists")
    status = models.MaintenanceStatus(**payload.model_dump())
    db.add(status)
    db.commit()
    db.refresh(status)
    return status

@router.get("/status/", response_model=List[schemas.MaintenanceStatusOut])
def list_statuses(db: Session = Depends(get_db)):
    return db.query(models.MaintenanceStatus).all()

@router.put("/status/{status_id}", response_model=schemas.MaintenanceStatusOut)
def update_status(status_id: int, payload: schemas.MaintenanceStatusCreate, db: Session = Depends(get_db)):
    status = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    status.name = payload.name
    db.commit()
    db.refresh(status)
    return status

@router.delete("/status/{status_id}")
def delete_status(status_id: int, db: Session = Depends(get_db)):
    status = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    db.delete(status)
    db.commit()
    return {"message": "Status deleted successfully"}

# ==============================
# Maintenance Requests CRUD
# ==============================

@router.post("/", response_model=schemas.MaintenanceRequestOut)
def create_request(payload: schemas.MaintenanceRequestCreate, db: Session = Depends(get_db)):
    # Optional: validate status exists
    status = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.id == payload.status_id).first()
    if not status:
        raise HTTPException(status_code=400, detail="Invalid status_id")
    mr = models.MaintenanceRequest(**payload.model_dump())
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return mr

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

    return query.all()

@router.put("/{mr_id}", response_model=schemas.MaintenanceRequestOut)
def update_request(mr_id: int, payload: schemas.MaintenanceRequestUpdate, db: Session = Depends(get_db)):
    mr = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")
    
    # Optional: validate status if being updated
    if payload.status_id:
        status = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.id == payload.status_id).first()
        if not status:
            raise HTTPException(status_code=400, detail="Invalid status_id")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(mr, key, value)

    db.commit()
    db.refresh(mr)
    return mr

@router.delete("/{mr_id}")
def delete_request(mr_id: int, db: Session = Depends(get_db)):
    mr = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Maintenance request not found")
    db.delete(mr)
    db.commit()
    return {"message": "Maintenance request deleted successfully"}
