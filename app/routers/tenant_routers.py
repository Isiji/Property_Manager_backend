# app/routers/tenant_router.py
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.tenant_schema import TenantCreate, TenantOut, TenantUpdate
from app import models
from app.crud import tenant as crud_tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.post("/", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return crud_tenant.create_tenant(db, payload)

@router.get("/", response_model=List[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return crud_tenant.get_tenants(db)

@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant_route(tenant_id: int, db: Session = Depends(get_db)):
    t = crud_tenant.get_tenant(db, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t

# Full update
@router.put("/{tenant_id}", response_model=TenantOut)
def update_tenant_put(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    t = crud_tenant.update_tenant(db, tenant_id, payload)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t

# Partial update (NEW)
@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant_patch(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    t = crud_tenant.update_tenant(db, tenant_id, payload)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t

@router.delete("/{tenant_id}", response_model=dict)
def delete_tenant_route(tenant_id: int, db: Session = Depends(get_db)):
    ok = crud_tenant.delete_tenant(db, tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"ok": True, "message": "Tenant deleted successfully"}

# ------- find by phone (for assigning existing) -------
@router.get("/by-phone", response_model=TenantOut)
def get_by_phone(phone: str = Query(...), db: Session = Depends(get_db)):
    t = crud_tenant.get_tenant_by_phone(db, phone)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t

# ------- assign existing tenant to a unit -------
class AssignExistingTenant(BaseModel):
    phone: str
    unit_id: int
    rent_amount: float
    start_date: date

@router.post("/assign-existing", response_model=dict)
def assign_existing(payload: AssignExistingTenant, db: Session = Depends(get_db)):
    tenant = crud_tenant.get_tenant_by_phone(db, payload.phone)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    lease = crud_tenant.assign_existing_tenant_to_unit(
        db=db,
        tenant=tenant,
        unit=unit,
        rent_amount=payload.rent_amount,
        start_date=payload.start_date,
    )
    return {
        "ok": True,
        "lease_id": lease.id,
        "tenant_id": tenant.id,
        "unit_id": unit.id,
        "start_date": lease.start_date.isoformat(),
        "rent_amount": str(lease.rent_amount) if lease.rent_amount is not None else None,
    }
