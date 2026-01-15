# app/routers/property_manager_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List

from app.dependencies import get_db
from app.schemas.property_manager_schema import (
    PropertyManagerCreate,
    PropertyManagerUpdate,
    PropertyManagerOut,
)
from app.models.user_models import PropertyManager
from app.auth.password_utils import hash_password
from app.utils.phone_utils import normalize_ke_phone

router = APIRouter(prefix="/managers", tags=["Property Managers"])


# ----------------------------
# Helpers
# ----------------------------
def _clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def _clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return normalize_ke_phone(phone)


def _exists_by_email_or_phone(db: Session, email: str | None, phone: str | None) -> bool:
    conds = []
    if email:
        conds.append(PropertyManager.email == email)
    if phone:
        conds.append(PropertyManager.phone == phone)
    if not conds:
        return False
    return db.query(db.query(PropertyManager.id).filter(or_(*conds)).exists()).scalar()


# ----------------------------
# Routes
# ----------------------------
@router.post("/", response_model=PropertyManagerOut, status_code=status.HTTP_201_CREATED)
def create_property_manager(payload: PropertyManagerCreate, db: Session = Depends(get_db)):
    """
    Create a property manager.
    NOTE: PropertyManager.password is NOT NULL in your model, so password must be saved.
    """
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    phone = _clean_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid Kenyan phone number")

    email = _clean_email(getattr(payload, "email", None))
    password = getattr(payload, "password", None)

    if not password:
        raise HTTPException(status_code=400, detail="Password is required for manager creation")

    if _exists_by_email_or_phone(db, email, phone):
        raise HTTPException(status_code=409, detail="Email or phone already registered for a manager")

    manager = PropertyManager(
        name=name,
        phone=phone,
        email=email,
        password=hash_password(password),
        id_number=getattr(payload, "id_number", None),
    )

    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


@router.get("/", response_model=List[PropertyManagerOut])
def list_property_managers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(PropertyManager)
        .order_by(PropertyManager.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/search", response_model=List[PropertyManagerOut])
def search_property_managers(q: str, db: Session = Depends(get_db), limit: int = 25):
    """
    Search managers by name/phone/email.
    Example: /managers/search?q=0712
    """
    query = (q or "").strip()
    if not query:
        return []

    phone_guess = None
    try:
        phone_guess = normalize_ke_phone(query)
    except Exception:
        phone_guess = None

    conds = [
        PropertyManager.name.ilike(f"%{query}%"),
        PropertyManager.email.ilike(f"%{query}%"),
        PropertyManager.phone.ilike(f"%{query}%"),
    ]
    if phone_guess:
        conds.append(PropertyManager.phone == phone_guess)

    rows = (
        db.query(PropertyManager)
        .filter(or_(*conds))
        .order_by(PropertyManager.id.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.get("/{manager_id}", response_model=PropertyManagerOut)
def get_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")
    return manager


@router.put("/{manager_id}", response_model=PropertyManagerOut)
def update_property_manager(manager_id: int, payload: PropertyManagerUpdate, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")

    data = payload.dict(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        manager.name = data["name"].strip() or manager.name

    if "email" in data:
        manager.email = _clean_email(data.get("email"))

    if "phone" in data and data["phone"] is not None:
        phone = _clean_phone(data["phone"])
        if not phone:
            raise HTTPException(status_code=400, detail="Invalid Kenyan phone number")
        manager.phone = phone

    if "password" in data and data["password"]:
        manager.password = hash_password(data["password"])

    if "id_number" in data:
        manager.id_number = data.get("id_number")

    db.commit()
    db.refresh(manager)
    return manager


@router.delete("/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")

    db.delete(manager)
    db.commit()
    return None
