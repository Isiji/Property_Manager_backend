# app/routers/service_charges.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from .. import models
from ..schemas import services_charges_schema as schemas
from ..dependencies import get_db

router = APIRouter(prefix="/service-charges", tags=["Service Charges"])


# Create a service charge
@router.post("/", response_model=schemas.ServiceChargeOut)
def create_service_charge(payload: schemas.ServiceChargeCreate, db: Session = Depends(get_db)):
    sc = models.ServiceCharge(**payload.dict())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


# List all service charges with optional filters
@router.get("/", response_model=List[schemas.ServiceChargeOut])
def list_service_charges(
    db: Session = Depends(get_db),
    tenant_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    service_type: Optional[str] = None,
    start_date: Optional[datetime] = Query(None, description="Filter charges from this date (YYYY-MM-DD)"),
    end_date: Optional[datetime] = Query(None, description="Filter charges until this date (YYYY-MM-DD)"),
):
    query = db.query(models.ServiceCharge)

    if tenant_id:
        query = query.filter(models.ServiceCharge.tenant_id == tenant_id)
    if unit_id:
        query = query.filter(models.ServiceCharge.unit_id == unit_id)
    if service_type:
        query = query.filter(models.ServiceCharge.service_type.ilike(f"%{service_type}%"))
    if start_date:
        query = query.filter(models.ServiceCharge.date >= start_date)
    if end_date:
        query = query.filter(models.ServiceCharge.date <= end_date)

    return query.all()


# Update service charge
@router.put("/{sc_id}", response_model=schemas.ServiceChargeOut)
def update_service_charge(sc_id: int, payload: schemas.ServiceChargeUpdate, db: Session = Depends(get_db)):
    sc = db.query(models.ServiceCharge).filter(models.ServiceCharge.id == sc_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Service charge not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(sc, key, value)

    db.commit()
    db.refresh(sc)
    return sc


# Delete service charge
@router.delete("/{sc_id}")
def delete_service_charge(sc_id: int, db: Session = Depends(get_db)):
    sc = db.query(models.ServiceCharge).filter(models.ServiceCharge.id == sc_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Service charge not found")

    db.delete(sc)
    db.commit()
    return {"message": "Service charge deleted successfully"}
