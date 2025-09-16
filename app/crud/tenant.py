# app/crud/tenant.py
from sqlalchemy.orm import Session
from app import models
from app.schemas.tenant_schema import TenantCreate, TenantUpdate
from fastapi import HTTPException

def create_tenant(db: Session, payload: TenantCreate):
    # check duplicates
    exists = db.query(models.Tenant).filter(
        (models.Tenant.email == payload.email) | (models.Tenant.phone == payload.phone)
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Tenant with email or phone already exists")

    tenant = models.Tenant(**payload.dict())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
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
    tenant = get_tenant(db, tenant_id)
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}
