# app/crud/lease_crud.py
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from app import models
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate


def create_lease(db: Session, payload: LeaseCreate) -> models.Lease:
    """
    Create a lease and mark unit.occupied = 1.
    Ends any existing active lease for this unit before creating a new one.
    """
    # End any existing active lease on the unit
    active = (
        db.query(models.Lease)
        .filter(models.Lease.unit_id == payload.unit_id, models.Lease.active == 1)
        .first()
    )
    if active:
        active.active = 0
        active.end_date = date.today()

    lease = models.Lease(
        tenant_id=payload.tenant_id,
        unit_id=payload.unit_id,
        start_date=payload.start_date or date.today(),
        end_date=payload.end_date,          # can be None
        rent_amount=payload.rent_amount,
        active=1 if (payload.active is None) else payload.active,
    )
    db.add(lease)

    # Mark unit occupied if this lease is active
    unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
    if unit and lease.active == 1:
        unit.occupied = 1

    db.commit()
    db.refresh(lease)
    return lease


def get_lease(db: Session, lease_id: int) -> Optional[models.Lease]:
    return db.query(models.Lease).filter(models.Lease.id == lease_id).first()


def list_leases(db: Session, skip: int = 0, limit: int = 100) -> List[models.Lease]:
    return db.query(models.Lease).offset(skip).limit(limit).all()


def update_lease(db: Session, lease_id: int, payload: LeaseUpdate) -> Optional[models.Lease]:
    lease = get_lease(db, lease_id)
    if not lease:
        return None

    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(lease, k, v)

    # Keep unit occupancy consistent if 'active' flipped
    if "active" in data:
        unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
        if unit:
            unit.occupied = 1 if lease.active == 1 else 0

    db.commit()
    db.refresh(lease)
    return lease


def end_lease(db: Session, lease_id: int) -> Optional[models.Lease]:
    """
    End a lease (set active=0, end_date=today), set unit.occupied=0 if this is the active lease.
    """
    lease = get_lease(db, lease_id)
    if not lease:
        return None

    lease.active = 0
    if not lease.end_date:
        lease.end_date = date.today()

    # Free the unit
    unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
    if unit:
        unit.occupied = 0

    db.commit()
    db.refresh(lease)
    return lease


def active_lease_for_unit(db: Session, unit_id: int) -> Optional[models.Lease]:
    return (
        db.query(models.Lease)
        .filter(models.Lease.unit_id == unit_id, models.Lease.active == 1)
        .first()
    )


def active_lease_for_tenant(db: Session, tenant_id: int) -> Optional[models.Lease]:
    return (
        db.query(models.Lease)
        .filter(models.Lease.tenant_id == tenant_id, models.Lease.active == 1)
        .first()
    )
