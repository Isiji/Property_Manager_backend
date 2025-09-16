# app/crud/unit.py
from sqlalchemy.orm import Session
from app import models, schemas
from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.exc import NoResultFound
from app.schemas.tenant_schema import TenantOut
from app.crud import tenant as tenant_crud

def create_unit(db: Session, unit: schemas.UnitCreate):
    new_unit = models.Unit(
        number=unit.number,
        rent_amount=unit.rent_amount,
        property_id=unit.property_id
    )
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    return new_unit

def get_units(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Unit).offset(skip).limit(limit).all()

def get_unit(db: Session, unit_id: int):
    return db.query(models.Unit).filter(models.Unit.id == unit_id).first()

def update_unit(db: Session, unit_id: int, unit_update: schemas.UnitUpdate):
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

def delete_unit(db: Session, unit_id: int):
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        return None
    db.delete(unit)
    db.commit()
    return unit


def get_units_by_property(db: Session, property_id: int):
    return db.query(models.Unit).filter(models.Unit.property_id == property_id).all()

# app/crud/unit.py
def get_available_units(db: Session, property_id: int = None):
    query = db.query(models.Unit).outerjoin(models.Lease)
    query = query.filter((models.Lease.id == None) | (models.Lease.active == 0))
    if property_id:
        query = query.filter(models.Unit.property_id == property_id)
    return query.all()

def get_occupied_units(db: Session, property_id: int = None):
    query = db.query(models.Unit).join(models.Lease).filter(models.Lease.active == 1)
    if property_id:
        query = query.filter(models.Unit.property_id == property_id)
    return query.all()

def search_units(db: Session, query_str: str):
    return db.query(models.Unit).filter(models.Unit.number.ilike(f"%{query_str}%")).all()

def get_unit_tenant(db: Session, unit_id: int):
    lease = db.query(models.Lease).filter(
        models.Lease.unit_id == unit_id, models.Lease.active == 1
    ).first()
    return lease.tenant if lease else None
