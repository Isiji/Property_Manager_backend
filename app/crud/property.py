from sqlalchemy.orm import Session
from app import models, schemas

# Create
def create_property(db: Session, payload: schemas.PropertyCreate):
    prop = models.Property(**payload.dict())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop

# Get all
def get_properties(db: Session):
    return db.query(models.Property).all()

# Get single
def get_property(db: Session, property_id: int):
    return db.query(models.Property).filter(models.Property.id == property_id).first()

# Update
def update_property(db: Session, property_id: int, payload: schemas.PropertyUpdate):
    prop = get_property(db, property_id)
    if not prop:
        return None
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(prop, field, value)
    db.commit()
    db.refresh(prop)
    return prop

# Delete
def delete_property(db: Session, property_id: int):
    prop = get_property(db, property_id)
    if not prop:
        return None
    db.delete(prop)
    db.commit()
    return prop

# Helpers
def get_properties_by_landlord(db: Session, landlord_id: int):
    return db.query(models.Property).filter(models.Property.landlord_id == landlord_id).all()

def get_properties_by_manager(db: Session, manager_id: int):
    return db.query(models.Property).filter(models.Property.manager_id == manager_id).all()

def get_property_with_units(db: Session, property_id: int):
    return db.query(models.Property).filter(models.Property.id == property_id).first()
