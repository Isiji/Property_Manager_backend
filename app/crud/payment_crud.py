# app/crud/payment_crud.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models
from app.schemas.payment_schema import PaymentCreate, PaymentUpdate


def _ensure_active_lease(
    db: Session, tenant_id: int, unit_id: int, lease_id: Optional[int]
) -> Optional[int]:
    """
    If lease_id is provided and exists, use it.
    Otherwise, try to find an active lease for (tenant_id, unit_id).
    If none found, return None (caller decides whether to create one).
    """
    if lease_id:
        lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
        if lease:
            return lease.id

    active = (
        db.query(models.Lease)
        .filter(
            models.Lease.tenant_id == tenant_id,
            models.Lease.unit_id == unit_id,
            models.Lease.active == 1,
        )
        .first()
    )
    return active.id if active else None


def create_payment(db: Session, payload: PaymentCreate) -> models.Payment:
    """
    Creates a payment row. If no lease_id provided:
      - try to attach to existing active lease for (tenant, unit)
      - (optional) you may auto-create a lease here, but that is business-specific.
        For now, we just attach if available; otherwise keep lease_id as None.
    If status is PAID and paid_date is missing, set paid_date = today.
    Enforces unique (lease_id, period) at DB level; raises 409-friendly error on violation.
    """
    lease_id = _ensure_active_lease(
        db, tenant_id=payload.tenant_id, unit_id=payload.unit_id, lease_id=payload.lease_id
    )

    # If you want to auto-create a lease when missing, uncomment this block:
    # if lease_id is None:
    #     unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
    #     if unit:
    #         new_lease = models.Lease(
    #             tenant_id=payload.tenant_id,
    #             unit_id=payload.unit_id,
    #             rent_amount=unit.rent_amount,
    #             start_date=datetime.utcnow().date(),
    #             active=1,
    #         )
    #         db.add(new_lease)
    #         db.commit()
    #         db.refresh(new_lease)
    #         lease_id = new_lease.id

    to_create = models.Payment(
        tenant_id=payload.tenant_id,
        unit_id=payload.unit_id,
        lease_id=lease_id,
        amount=payload.amount,
        period=payload.period,
        status=payload.status,
        paid_date=payload.paid_date or (
            # Default paid_date to today if marking as paid
            (datetime.utcnow().date() if str(payload.status) == "PaymentStatus.paid" or payload.status == models.payment_models.PaymentStatus.paid else None)
        ),
    )

    db.add(to_create)
    try:
        db.commit()
        db.refresh(to_create)
        return to_create
    except IntegrityError as e:
        db.rollback()
        # Likely unique violation (lease_id, period)
        raise ValueError("Payment for this lease and period already exists") from e


def get_payment(db: Session, payment_id: int) -> Optional[models.Payment]:
    return db.query(models.Payment).filter(models.Payment.id == payment_id).first()


def get_payments(db: Session, skip: int = 0, limit: int = 100) -> List[models.Payment]:
    return db.query(models.Payment).order_by(models.Payment.created_at.desc()).offset(skip).limit(limit).all()


def update_payment(db: Session, payment_id: int, payload: PaymentUpdate) -> Optional[models.Payment]:
    p = get_payment(db, payment_id)
    if not p:
        return None

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)

    # If switching to PAID and no paid_date, stamp today.
    if "status" in data and p.status == models.payment_models.PaymentStatus.paid and p.paid_date is None:
        p.paid_date = datetime.utcnow().date()

    db.commit()
    db.refresh(p)
    return p


def delete_payment(db: Session, payment_id: int) -> bool:
    p = get_payment(db, payment_id)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def get_payments_by_tenant(db: Session, tenant_id: int) -> List[models.Payment]:
    return (
        db.query(models.Payment)
        .filter(models.Payment.tenant_id == tenant_id)
        .order_by(models.Payment.created_at.desc())
        .all()
    )


def get_payments_by_unit(db: Session, unit_id: int) -> List[models.Payment]:
    return (
        db.query(models.Payment)
        .filter(models.Payment.unit_id == unit_id)
        .order_by(models.Payment.created_at.desc())
        .all()
    )


def get_payments_by_lease(db: Session, lease_id: int) -> List[models.Payment]:
    return (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease_id)
        .order_by(models.Payment.created_at.desc())
        .all()
    )


def get_payments_by_date_range(db: Session, start_date: datetime, end_date: datetime) -> List[models.Payment]:
    # Use created_at (your previous code referenced a non-existent "date" column)
    return (
        db.query(models.Payment)
        .filter(models.Payment.created_at >= start_date, models.Payment.created_at <= end_date)
        .order_by(models.Payment.created_at.desc())
        .all()
    )
