# app/crud/payments.py
from sqlalchemy.orm import Session
from datetime import datetime
from .. import models, schemas
from typing import List

def create_payment(db: Session, payload: schemas.PaymentCreate):
    p = models.Payment(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)

    # Auto-create lease if not exists
    active_lease = db.query(models.Lease).filter(
        models.Lease.unit_id == payload.unit_id,
        models.Lease.tenant_id == payload.tenant_id,
        models.Lease.active == 1
    ).first()

    if not active_lease:
        unit = db.query(models.Unit).filter(models.Unit.id == payload.unit_id).first()
        lease = models.Lease(
            tenant_id=payload.tenant_id,
            unit_id=payload.unit_id,
            rent_amount=unit.rent_amount,
            active=1
        )
        db.add(lease)
        db.commit()
        db.refresh(lease)

    return p
def get_payment(db: Session, payment_id: int):
    return db.query(models.Payment).filter(models.Payment.id == payment_id).first()

def get_payments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Payment).offset(skip).limit(limit).all()

def update_payment(db: Session, payment_id: int, payload: schemas.PaymentUpdate):
    p = get_payment(db, payment_id)
    if not p:
        return None
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(p, key, value)
    db.commit()
    db.refresh(p)
    return p

def delete_payment(db: Session, payment_id: int):
    p = get_payment(db, payment_id)
    if not p:
        return None
    db.delete(p)
    db.commit()
    return p

# Get payments by tenant
def get_payments_by_tenant(db: Session, tenant_id: int) -> List[models.Payment]:
    return db.query(models.Payment).filter(models.Payment.tenant_id == tenant_id).all()

# Get payments by unit
def get_payments_by_unit(db: Session, unit_id: int) -> List[models.Payment]:
    return db.query(models.Payment).filter(models.Payment.unit_id == unit_id).all()

# Get payments by lease
def get_payments_by_lease(db: Session, lease_id: int) -> List[models.Payment]:
    return db.query(models.Payment).filter(models.Payment.lease_id == lease_id).all()

# Get payments by date range
def get_payments_by_date_range(db: Session, start_date: datetime, end_date: datetime) -> List[models.Payment]:
    return db.query(models.Payment).filter(
        models.Payment.date >= start_date,
        models.Payment.date <= end_date
    ).all()
