# app/crud/tenant.py
from sqlalchemy.orm import Session
from app import models
from app.schemas.tenant_schema import TenantCreate, TenantUpdate, TenantSelfRegister
from fastapi import HTTPException
from datetime import date

def create_tenant(db: Session, payload: TenantCreate):
    # check duplicates
    exists = db.query(models.Tenant).filter(
        (models.Tenant.email == payload.email) | (models.Tenant.phone == payload.phone)
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Tenant with email or phone already exists")

    # create tenant
    tenant = models.Tenant(**payload.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # ✅ if tenant is linked to a unit, mark unit as occupied and create lease
    if tenant.unit_id:
        unit = db.query(models.Unit).filter(models.Unit.id == tenant.unit_id).first()
        if not unit:
            raise HTTPException(status_code=404, detail="Assigned unit not found")

        if unit.occupied:
            raise HTTPException(status_code=400, detail="Unit is already occupied")

        unit.occupied = 1

        lease = models.Lease(
            tenant_id=tenant.id,
            unit_id=tenant.unit_id,
            start_date=date.today(),
            active=1
        )
        db.add(lease)

        db.commit()
        db.refresh(tenant)
        db.refresh(unit)
        db.refresh(lease)

    return tenant

def get_tenants(db: Session):
    return db.query(models.Tenant).all()

def get_tenant(db: Session, tenant_id: int):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant

def update_tenant(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = get_tenant(db, tenant_id)  # reuse get_tenant
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(tenant, key, value)
    db.commit()
    db.refresh(tenant)
    return tenant

def delete_tenant(db: Session, tenant_id: int):
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # ✅ free up unit + close lease
    if tenant.unit_id:
        unit = db.query(models.Unit).filter(models.Unit.id == tenant.unit_id).first()
        if unit:
            unit.occupied = 0

        lease = db.query(models.Lease).filter(
            models.Lease.tenant_id == tenant.id,
            models.Lease.active == 1
        ).first()
        if lease:
            lease.active = 0
            lease.end_date = date.today()

    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully and unit marked vacant"}