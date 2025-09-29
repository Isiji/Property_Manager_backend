from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.user_models import PropertyManager

def get_property_manager(db: Session, manager_id: int) -> PropertyManager | None:
    return db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()

def get_property_managers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(PropertyManager).offset(skip).limit(limit).all()

def create_property_manager(db: Session, name: str, phone: str, email: str | None = None) -> PropertyManager:
    obj = PropertyManager(name=name, phone=phone, email=email)
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate phone or email")

def update_property_manager(db: Session, manager: PropertyManager, data: dict) -> PropertyManager:
    for key, value in data.items():
        if value is not None and hasattr(manager, key):
            setattr(manager, key, value)
    try:
        db.commit()
        db.refresh(manager)
        return manager
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate phone or email")

def delete_property_manager(db: Session, manager: PropertyManager):
    db.delete(manager)
    db.commit()
