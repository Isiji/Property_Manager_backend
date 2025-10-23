from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional
from datetime import date
from app import models, schemas

def get_tenant(db: Session, tenant_id: int) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()

def get_tenant_by_phone(db: Session, phone: str) -> Optional[models.Tenant]:
    return db.query(models.Tenant).filter(models.Tenant.phone == phone).first()

def get_tenants(db: Session):
    return db.query(models.Tenant).all()

def create_tenant(db: Session, payload: schemas.TenantCreate) -> models.Tenant:
    # Unique phone guard
    existing = get_tenant_by_phone(db, payload.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with phone {payload.phone} already exists (id={existing.id})"
        )

    t = models.Tenant(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        property_id=payload.property_id,
        unit_id=payload.unit_id,
        password=None,  # optional
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def update_tenant(db: Session, tenant_id: int, payload: schemas.TenantUpdate):
    t = get_tenant(db, tenant_id)
    if not t:
        return None
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t

def delete_tenant(db: Session, tenant_id: int) -> bool:
    t = get_tenant(db, tenant_id)
    if not t:
        return False

    # Mark active lease inactive and set unit vacant
    for lease in t.leases:
        if lease.active == 1:
            lease.active = 0
            if lease.unit:
                lease.unit.occupied = 0

    db.delete(t)
    db.commit()
    return True

def assign_existing_tenant_to_unit(
    db: Session,
    tenant: models.Tenant,
    unit: models.Unit,
    rent_amount: float,
    start_date: date,
) -> models.Lease:
    """
    Assign an existing tenant to a (vacant) unit by creating an active lease.
    Enforces: unit must be vacant, tenant must not already have an active lease.
    Also updates tenant.unit_id so downstream queries are consistent.
    """
    # Guard: unit must be vacant
    if unit.occupied == 1:
        raise HTTPException(status_code=400, detail="Unit is already occupied")

    # Guard: tenant must not have an active lease already
    active = (
        db.query(models.Lease)
        .filter(models.Lease.tenant_id == tenant.id, models.Lease.active == 1)
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="Tenant already has an active lease")

    # ✅ keep model consistent
    tenant.unit_id = unit.id

    lease = models.Lease(
        tenant_id=tenant.id,
        unit_id=unit.id,
        start_date=start_date,
        end_date=None,
        rent_amount=rent_amount,
        active=1,
    )
    unit.occupied = 1

    db.add(lease)
    db.commit()
    db.refresh(lease)
    return lease
