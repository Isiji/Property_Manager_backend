from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.user_models import Admin

def create_admin(db: Session, name: str, email: str, phone: str | None, password: str, id_number: str | None = None) -> Admin:
    obj = Admin(name=name, email=email, phone=phone, password=password, id_number=id_number)
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError as e:
        db.rollback()
        msg = str(e.orig).lower()
        if "email" in msg:
            raise HTTPException(status_code=400, detail="Email already registered")
        if "phone" in msg:
            raise HTTPException(status_code=400, detail="Phone already registered")
        raise HTTPException(status_code=400, detail="Duplicate entry")

def get_admin(db: Session, admin_id: int) -> Admin | None:
    return db.query(Admin).filter(Admin.id == admin_id).first()

def get_admins(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Admin).offset(skip).limit(limit).all()

def update_admin(db: Session, admin: Admin, data: dict) -> Admin:
    for key, value in data.items():
        if value is not None and hasattr(admin, key):
            setattr(admin, key, value)
    try:
        db.commit()
        db.refresh(admin)
        return admin
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate email or phone")

def delete_admin(db: Session, admin: Admin):
    db.delete(admin)
    db.commit()
