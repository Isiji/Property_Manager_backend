from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from app import models
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate


def create_lease(db: Session, payload: LeaseCreate) -> models.Lease:
    is_active = 1 if payload.active is None else int(payload.active)

    lease = models.Lease(
        tenant_id=payload.tenant_id,
        unit_id=payload.unit_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        rent_amount=payload.rent_amount,
        active=is_active,
    )
    db.add(lease)

    # Mark unit occupied if lease active
    if is_active == 1:
        unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
        if unit:
            unit.occupied = 1

    db.commit()
    db.refresh(lease)
    return lease


def get_lease(db: Session, lease_id: int) -> Optional[models.Lease]:
    return db.query(models.Lease).filter(models.Lease.id == lease_id).first()


def update_lease(db: Session, lease_id: int, payload: LeaseUpdate) -> Optional[models.Lease]:
    lease = get_lease(db, lease_id)
    if not lease:
        return None

    if payload.start_date is not None:
        lease.start_date = payload.start_date
    if payload.end_date is not None:
        lease.end_date = payload.end_date
    if payload.rent_amount is not None:
        lease.rent_amount = payload.rent_amount
    if payload.active is not None:
        lease.active = int(payload.active)
        unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
        if unit:
            unit.occupied = 1 if lease.active == 1 else 0

    db.commit()
    db.refresh(lease)
    return lease


def end_lease(db: Session, lease_id: int, end_date: datetime) -> Optional[models.Lease]:
    lease = get_lease(db, lease_id)
    if not lease:
        return None

    lease.end_date = end_date
    lease.active = 0

    unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
    if unit:
        unit.occupied = 0

    db.commit()
    db.refresh(lease)
    return lease


def delete_lease(db: Session, lease_id: int) -> bool:
    lease = get_lease(db, lease_id)
    if not lease:
        return False

    # If deleting an active lease, mark unit vacant
    if lease.active == 1:
        unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
        if unit:
            unit.occupied = 0

    db.delete(lease)
    db.commit()
    return True
