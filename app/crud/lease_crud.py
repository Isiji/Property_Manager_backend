# app/crud/lease_crud.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate


def _recompute_unit_occupied(db: Session, unit_id: int) -> None:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        return

    active_exists = (
        db.query(models.Lease)
        .filter(models.Lease.unit_id == unit_id, models.Lease.active == 1)
        .first()
    )
    unit.occupied = 1 if active_exists else 0


def create_lease(db: Session, payload: LeaseCreate) -> models.Lease:
    unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
    if not unit:
        raise ValueError("Unit not found")

    # A single unit cannot have 2 active leases at the same time.
    active_for_unit = (
        db.query(models.Lease)
        .filter(models.Lease.unit_id == payload.unit_id, models.Lease.active == 1)
        .first()
    )
    if active_for_unit and int(payload.active or 1) == 1:
        raise ValueError("Unit already has an active lease")

    is_active = 1 if payload.active is None else int(payload.active)

    lease = models.Lease(
        tenant_id=payload.tenant_id,
        unit_id=payload.unit_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        rent_amount=payload.rent_amount,
        active=is_active,
        terms_text=payload.terms_text,
        terms_accepted=0 if payload.terms_accepted is None else int(payload.terms_accepted),
        terms_accepted_at=payload.terms_accepted_at,
    )
    db.add(lease)
    db.flush()

    _recompute_unit_occupied(db, payload.unit_id)

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
        if int(payload.active) == 1:
            active_for_unit = (
                db.query(models.Lease)
                .filter(
                    models.Lease.unit_id == lease.unit_id,
                    models.Lease.active == 1,
                    models.Lease.id != lease.id,
                )
                .first()
            )
            if active_for_unit:
                raise ValueError("Unit already has another active lease")
        lease.active = int(payload.active)

    if payload.terms_text is not None:
        lease.terms_text = payload.terms_text
    if payload.terms_accepted is not None:
        lease.terms_accepted = int(payload.terms_accepted)
    if payload.terms_accepted_at is not None:
        lease.terms_accepted_at = payload.terms_accepted_at

    _recompute_unit_occupied(db, lease.unit_id)

    db.commit()
    db.refresh(lease)
    return lease


def end_lease(db: Session, lease_id: int, end_date: datetime) -> Optional[models.Lease]:
    lease = get_lease(db, lease_id)
    if not lease:
        return None

    lease.end_date = end_date
    lease.active = 0

    _recompute_unit_occupied(db, lease.unit_id)

    db.commit()
    db.refresh(lease)
    return lease


def delete_lease(db: Session, lease_id: int) -> bool:
    lease = get_lease(db, lease_id)
    if not lease:
        return False

    unit_id = lease.unit_id
    db.delete(lease)
    db.flush()

    _recompute_unit_occupied(db, unit_id)

    db.commit()
    return True


def list_leases_for_tenant(db: Session, tenant_id: int):
    return (
        db.query(models.Lease)
        .filter(models.Lease.tenant_id == tenant_id)
        .order_by(models.Lease.active.desc(), models.Lease.start_date.desc())
        .all()
    )


def list_leases_for_landlord(db: Session, landlord_id: int):
    return (
        db.query(models.Lease)
        .join(models.Unit, models.Unit.id == models.Lease.unit_id)
        .join(models.Property, models.Property.id == models.Unit.property_id)
        .filter(models.Property.landlord_id == landlord_id)
        .order_by(models.Lease.active.desc(), models.Lease.start_date.desc())
        .all()
    )


def list_leases_for_manager(db: Session, manager_id: int):
    return (
        db.query(models.Lease)
        .join(models.Unit, models.Unit.id == models.Lease.unit_id)
        .join(models.Property, models.Property.id == models.Unit.property_id)
        .filter(models.Property.manager_id == manager_id)
        .order_by(models.Lease.active.desc(), models.Lease.start_date.desc())
        .all()
    )