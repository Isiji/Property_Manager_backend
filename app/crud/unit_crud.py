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

    lease = (
        db.query(models.Lease)
        .filter(
            models.Lease.unit_id == unit.id,
            models.Lease.active == 1,
        )
        .order_by(models.Lease.id.desc())
        .first()
    )

    tenant = None
    if lease:
        tenant = (
            db.query(models.Tenant)
            .filter(models.Tenant.id == lease.tenant_id)
            .first()
        )

    return {
        "id": unit.id,
        "number": unit.number,
        "rent_amount": unit.rent_amount,
        "property_id": unit.property_id,
        "occupied": unit.occupied,
        "tenant": tenant,
        "lease": lease,
    }


def _create_audit_log(
    db: Session,
    *,
    property_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    message: str,
    actor_role: str = "system",
    actor_id: Optional[int] = None,
) -> None:
    audit = models.AuditLog(
        property_id=property_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        actor_role=actor_role,
        actor_id=actor_id,
    )
    db.add(audit)


def _create_notification(
    db: Session,
    *,
    user_id: int,
    user_type: str,
    title: str,
    message: str,
    channel: str = "in_app",
) -> None:
    notification = models.Notification(
        user_id=user_id,
        user_type=user_type,
        title=title,
        message=message,
        channel=channel,
        is_read=False,
    )
    db.add(notification)


def update_unit(db: Session, unit_id: int, unit_update: schemas.UnitUpdate) -> Optional[models.Unit]:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        return None

    old_number = unit.number
    old_rent = float(unit.rent_amount or 0)

    number_changed = False
    rent_changed = False

    if unit_update.number is not None and unit_update.number != unit.number:
        unit.number = unit_update.number
        number_changed = True

    if unit_update.rent_amount is not None:
        new_rent = float(unit_update.rent_amount or 0)
        if new_rent != old_rent:
            unit.rent_amount = new_rent
            rent_changed = True

    active_lease = (
        db.query(models.Lease)
        .filter(
            models.Lease.unit_id == unit.id,
            models.Lease.active == 1,
        )
        .order_by(models.Lease.id.desc())
        .first()
    )

    tenant = None
    if active_lease and getattr(active_lease, "tenant_id", None):
        tenant = (
            db.query(models.Tenant)
            .filter(models.Tenant.id == active_lease.tenant_id)
            .first()
        )

    property_obj = None
    if getattr(unit, "property_id", None):
        property_obj = (
            db.query(models.Property)
            .filter(models.Property.id == unit.property_id)
            .first()
        )

    if rent_changed:
        new_rent = float(unit.rent_amount or 0)

        # Sync only the ACTIVE lease for this unit
        if active_lease:
            active_lease.rent_amount = new_rent

        _create_audit_log(
            db,
            property_id=unit.property_id,
            action="UPDATE_UNIT_RENT",
            entity_type="unit",
            entity_id=unit.id,
            message=(
                f"Unit {old_number} rent changed from KES {old_rent:.2f} "
                f"to KES {new_rent:.2f}. "
                f"Active lease synced: {'yes' if active_lease else 'no'}."
            ),
            actor_role="system",
            actor_id=None,
        )

        if tenant:
            _create_notification(
                db,
                user_id=tenant.id,
                user_type="tenant",
                title="Rent Updated",
                message=(
                    f"Your monthly rent for unit {unit.number} "
                    f"has changed from KES {old_rent:.2f} "
                    f"to KES {new_rent:.2f}."
                ),
                channel="in_app",
            )

        if property_obj and getattr(property_obj, "landlord_id", None):
            _create_notification(
                db,
                user_id=property_obj.landlord_id,
                user_type="landlord",
                title="Unit Rent Updated",
                message=(
                    f"Rent for unit {unit.number} was updated from "
                    f"KES {old_rent:.2f} to KES {new_rent:.2f}."
                ),
                channel="in_app",
            )

        if getattr(property_obj, "manager_id", None):
            _create_notification(
                db,
                user_id=property_obj.manager_id,
                user_type="manager",
                title="Unit Rent Updated",
                message=(
                    f"Rent for unit {unit.number} was updated from "
                    f"KES {old_rent:.2f} to KES {new_rent:.2f}."
                ),
                channel="in_app",
            )

    if number_changed:
        _create_audit_log(
            db,
            property_id=unit.property_id,
            action="UPDATE_UNIT_NUMBER",
            entity_type="unit",
            entity_id=unit.id,
            message=f"Unit number changed from {old_number} to {unit.number}.",
            actor_role="system",
            actor_id=None,
        )

    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit_id: int) -> models.Unit:
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    tenant_count = (
        db.query(func.count(models.Tenant.id))
        .filter(models.Tenant.unit_id == unit.id)
        .scalar()
    )
    if tenant_count and tenant_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete unit while tenants exist on it. End the lease and reassign/cleanup first.",
        )

    lease_count = (
        db.query(func.count(models.Lease.id))
        .filter(models.Lease.unit_id == unit.id)
        .scalar()
    )
    if lease_count and lease_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete unit while leases exist. Delete/cleanup leases first.",
        )

    db.delete(unit)
    db.commit()
    return unit


def search_units(db: Session, q: str) -> List[models.Unit]:
    q = (q or "").strip()
    if not q:
        return []

    return (
        db.query(models.Unit)
        .filter(models.Unit.number.ilike(f"%{q}%"))
        .order_by(models.Unit.id.desc())
        .all()
    )


def get_units_by_property(db: Session, property_id: int) -> List[models.Unit]:
    return (
        db.query(models.Unit)
        .filter(models.Unit.property_id == property_id)
        .order_by(models.Unit.id.desc())
        .all()
    )


def get_available_units(db: Session) -> List[models.Unit]:
    return (
        db.query(models.Unit)
        .filter(models.Unit.occupied == 0)
        .order_by(models.Unit.id.desc())
        .all()
    )


def get_occupied_units(db: Session) -> List[models.Unit]:
    return (
        db.query(models.Unit)
        .filter(models.Unit.occupied == 1)
        .order_by(models.Unit.id.desc())
        .all()
    )


def get_unit_tenant(db: Session, unit_id: int):
    active_lease = (
        db.query(models.Lease)
        .filter(
            models.Lease.unit_id == unit_id,
            models.Lease.active == 1,
        )
        .order_by(models.Lease.id.desc())
        .first()
    )
    if not active_lease:
        return None

    return (
        db.query(models.Tenant)
        .filter(models.Tenant.id == active_lease.tenant_id)
        .first()
    )