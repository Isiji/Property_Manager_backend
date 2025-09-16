# app/crud/service_charges.py
from sqlalchemy.orm import Session
from datetime import datetime
from .. import models, schemas

def create_service_charge(db: Session, payload: schemas.ServiceChargeCreate):
    charge = models.ServiceCharge(
        tenant_id=payload.tenant_id,
        unit_id=payload.unit_id,
        service_type=payload.service_type,
        amount=payload.amount,
        date=datetime.utcnow()
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge

def get_service_charge(db: Session, charge_id: int):
    return db.query(models.ServiceCharge).filter(models.ServiceCharge.id == charge_id).first()

def list_service_charges(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.ServiceCharge).offset(skip).limit(limit).all()

def update_service_charge(db: Session, charge_id: int, payload: schemas.ServiceChargeUpdate):
    charge = db.query(models.ServiceCharge).filter(models.ServiceCharge.id == charge_id).first()
    if not charge:
        return None
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(charge, key, value)
    db.commit()
    db.refresh(charge)
    return charge

def delete_service_charge(db: Session, charge_id: int):
    charge = db.query(models.ServiceCharge).filter(models.ServiceCharge.id == charge_id).first()
    if not charge:
        return None
    db.delete(charge)
    db.commit()
    return charge
