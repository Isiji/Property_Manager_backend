# app/crud/admin_crud.py
from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user_models import Admin, SuperAdmin
from app.auth.password_utils import hash_password


def _clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def _clean_phone(phone: str | None) -> str | None:
    p = (phone or "").strip()
    return p or None


def create_admin(
    db: Session,
    name: str,
    email: str,
    phone: Optional[str],
    password: str,
    id_number: Optional[str] = None,
) -> Admin:
    name = (name or "").strip()
    email = _clean_email(email)
    phone = _clean_phone(phone)

    if not name:
        raise ValueError("name is required")
    if not email:
        raise ValueError("email is required")
    if not password or not password.strip():
        raise ValueError("password is required")

    # Uniqueness checks
    exists = (
        db.query(Admin)
        .filter(or_(Admin.email == email, Admin.phone == phone if phone else False))
        .first()
    )
    if exists:
        raise ValueError("Email or phone already registered for an admin")

    admin = Admin(
        name=name,
        email=email,
        phone=phone,
        password=hash_password(password),
        id_number=id_number,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def get_admin(db: Session, admin_id: int) -> Optional[Admin]:
    return db.query(Admin).filter(Admin.id == int(admin_id)).first()


def get_admins(db: Session, skip: int = 0, limit: int = 100) -> List[Admin]:
    return (
        db.query(Admin)
        .order_by(Admin.id.desc())
        .offset(int(skip))
        .limit(int(limit))
        .all()
    )


def update_admin(db: Session, admin: Admin, data: Dict[str, Any]) -> Admin:
    """
    data may include: name, email, phone, password, id_number
    password will be hashed if provided.
    """
    if not admin:
        raise ValueError("admin is required")

    # Normalize
    if "email" in data:
        data["email"] = _clean_email(data.get("email"))
    if "phone" in data:
        data["phone"] = _clean_phone(data.get("phone"))

    # If changing email/phone, enforce uniqueness
    new_email = data.get("email", None)
    new_phone = data.get("phone", None)

    if new_email and new_email != admin.email:
        exists = db.query(Admin).filter(Admin.email == new_email).first()
        if exists:
            raise ValueError("Email already registered for another admin")

    if new_phone and new_phone != admin.phone:
        exists = db.query(Admin).filter(Admin.phone == new_phone).first()
        if exists:
            raise ValueError("Phone already registered for another admin")

    # Apply fields
    if "name" in data and data["name"] is not None:
        admin.name = (data["name"] or "").strip() or admin.name

    if "email" in data:
        admin.email = data["email"] or admin.email

    if "phone" in data:
        admin.phone = data["phone"]

    if "id_number" in data:
        admin.id_number = data.get("id_number")

    if "password" in data and data["password"]:
        admin.password = hash_password(str(data["password"]))

    db.commit()
    db.refresh(admin)
    return admin


def delete_admin(db: Session, admin: Admin) -> None:
    db.delete(admin)
    db.commit()