from __future__ import annotations

from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas


def create_unit(db: Session, unit: schemas.UnitCreate) -> models.Unit:
    new_unit = models.Unit(
        number=unit.number,
        rent_amount=unit.rent_amount,
        property_id=unit.property_id,
        occupied=0,
    )
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    return new_unit


def get_units(db: Session, skip: int = 0, limit: int = 100) -> List[models.Unit]:
    return db.query(models.Unit).offset(skip).limit(limit).all()


def get_unit(db: Session, unit_id: int) -> Optional[dict]:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        return None

    # Current active lease (if any)
    lease = db.query(models.Lease).filter(
        models.Lease.unit_id == unit.id,
        models.Lease.active == 1
    ).first()

    # Tenant via active lease
    tenant = None
    if lease:
        tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()

    return {
        "id": unit.id,
        "number": unit.number,
        "rent_amount": unit.rent_amount,
        "property_id": unit.property_id,
        "occupied": unit.occupied,
        "tenant": tenant,
        "lease": lease
    }


def update_unit(db: Session, unit_id: int, unit_update: schemas.UnitUpdate) -> Optional[models.Unit]:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        return None

    if unit_update.number is not None:
        unit.number = unit_update.number
    if unit_update.rent_amount is not None:
        unit.rent_amount = unit_update.rent_amount

    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit_id: int) -> models.Unit:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    # Hard guard: block delete if any tenant references this unit
    tenant_count = db.query(func.count(models.Tenant.id)).filter(models.Tenant.unit_id == unit.id).scalar()
    if tenant_count and tenant_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete unit while tenants exist on it. End the lease and reassign/cleanup first.")

    # Block delete if any leases reference this unit (active or historical)
    lease_count = db.query(func.count(models.Lease.id)).filter(models.Lease.unit_id == unit.id).scalar()
    if lease_count and lease_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete unit while leases exist. Delete/cleanup leases first.")

    db.delete(unit)
    db.commit()
    return unit
