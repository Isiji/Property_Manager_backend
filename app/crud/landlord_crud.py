# app/crud/landlord_crud.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.user_models import Landlord

def get_landlord(db: Session, landlord_id: int) -> Landlord | None:
    return (
        db.query(Landlord)
        .options(joinedload(Landlord.properties))  # eager-load properties
        .filter(Landlord.id == landlord_id)
        .first()
    )

def get_landlords(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Landlord).offset(skip).limit(limit).all()

def create_landlord(db: Session, name: str, phone: str, email: str | None = None) -> Landlord:
    obj = Landlord(name=name, phone=phone, email=email)
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError as e:
        db.rollback()
        if "phone" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Phone number already registered")
        if "email" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Duplicate entry")

def update_landlord(db: Session, landlord: Landlord, data: dict) -> Landlord:
    for key, value in data.items():
        if value is not None and hasattr(landlord, key):
            setattr(landlord, key, value)
    try:
        db.commit()
        db.refresh(landlord)
        return landlord
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate phone or email")

def delete_landlord(db: Session, landlord: Landlord):
    db.delete(landlord)
    db.commit()

def search_landlords(db: Session, query: str, skip: int = 0, limit: int = 100):
    return (
        db.query(Landlord)
        .filter(
            (Landlord.name.ilike(f"%{query}%")) |
            (Landlord.phone.ilike(f"%{query}%")) |
            (Landlord.email.ilike(f"%{query}%"))
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
