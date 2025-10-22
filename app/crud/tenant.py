# app/crud/tenant.py
from sqlalchemy.orm import Session
from typing import Optional
from app import models
from app.schemas.tenant_schema import TenantCreate, TenantUpdate


def create_tenant(db: Session, payload: TenantCreate) -> models.Tenant:
    """
    Create ONLY the tenant record.
    Do NOT create a lease here. The UI will call the lease endpoint separately.
    Do NOT change unit.occupied here; that happens when a lease is created.
    """
    tenant = models.Tenant(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,              # can be None
        property_id=payload.property_id,
        unit_id=payload.unit_id,
        password=None,                    # optional – keep None unless you want to set it
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def get_tenants(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Tenant).offset(skip).limit(limit).all()


def get_tenant(db: Session, tenant_id: int) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()


def update_tenant(db: Session, tenant_id: int, payload: TenantUpdate) -> Optional[models.Tenant]:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return None

    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(tenant, k, v)

    db.commit()
    db.refresh(tenant)
    return tenant


def delete_tenant(db: Session, tenant_id: int) -> bool:
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return False

    # DO NOT toggle unit occupancy here; leases determine occupancy.
    db.delete(tenant)
    db.commit()
    return {"detail": "Tenant deleted successfully"  }
