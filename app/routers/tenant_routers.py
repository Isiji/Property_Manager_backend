# app/routers/tenant.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.tenant_schema import TenantCreate, TenantOut, TenantUpdate, TenantSelfRegister
from app.crud import tenant as crud_tenant
from app import crud, models
from fastapi import HTTPException

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.post("/", response_model=TenantOut)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return crud_tenant.create_tenant(db, payload)

@router.get("/", response_model=List[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return crud_tenant.get_tenants(db)

@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return crud_tenant.get_tenant(db, tenant_id)

@router.put("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    return crud_tenant.update_tenant(db, tenant_id, payload)

def delete_tenant(db: Session, tenant_id: int):
    tenant = get_tenant(db, tenant_id)
    
    # Set unit as vacant
    for lease in tenant.leases:
        if lease.active == 1:
            lease.active = 0
            if lease.unit:
                lease.unit.occupied = 0

    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

@router.post("/self-register", response_model=TenantOut)
def tenant_self_register(payload: TenantSelfRegister, db: Session = Depends(get_db)):
    # 1. Check property exists
    prop = crud.property_crud.get_property(db, payload.property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # 2. Check unit exists
    unit = db.query(models.Unit).filter(
        models.Unit.property_id == payload.property_id,
        models.Unit.number == payload.unit_number
    ).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # 3. Check if unit already has active lease
    active_lease = db.query(models.Lease).filter(
        models.Lease.unit_id == unit.id,
        models.Lease.active == 1
    ).first()
    if active_lease:
        raise HTTPException(status_code=400, detail="Unit is already occupied")

    # 4. Create tenant
    tenant = crud.tenant.create_tenant(db, payload)

    return tenant
