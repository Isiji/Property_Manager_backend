from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user_models import Tenant
from app.models.property_models import Unit, Lease
from app.schemas.tenant_schema import TenantCreate, TenantUpdate
from app.auth.password_utils import hash_password
from app.utils.phone_utils import normalize_ke_phone


def _clean_email(email: Optional[str]) -> Optional[str]:
    if email is None:
        return None
    email = email.strip().lower()
    return email or None


def get_tenants(db: Session):
    return db.query(Tenant).order_by(Tenant.id.desc()).all()


def get_tenant(db: Session, tenant_id: int):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_tenant_by_phone(db: Session, phone: str):
    normalized = normalize_ke_phone(phone)
    if not normalized:
        return None
    return db.query(Tenant).filter(Tenant.phone == normalized).first()


def create_tenant(db: Session, payload: TenantCreate):
    try:
        normalized_phone = normalize_ke_phone(payload.phone)
        if not normalized_phone:
            raise HTTPException(
                status_code=400,
                detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format.",
            )

        email = _clean_email(payload.email)

        existing_phone = db.query(Tenant).filter(Tenant.phone == normalized_phone).first()
        if existing_phone:
            raise HTTPException(status_code=409, detail="Phone already registered for a tenant")

        if email:
            existing_email = db.query(Tenant).filter(func.lower(Tenant.email) == email).first()
            if existing_email:
                raise HTTPException(status_code=409, detail="Email already registered for a tenant")

        unit = db.query(Unit).filter(Unit.id == payload.unit_id).first()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")

        if unit.property_id != payload.property_id:
            raise HTTPException(status_code=400, detail="Selected unit does not belong to the given property")

        password_hash = hash_password(payload.password) if payload.password else None

        tenant = Tenant(
            name=payload.name.strip(),
            phone=normalized_phone,
            email=email,
            property_id=payload.property_id,
            unit_id=payload.unit_id,
            password=password_hash,
            id_number=(payload.id_number.strip() if payload.id_number else None),
        )

        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def update_tenant(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return None

    try:
        data = payload.model_dump(exclude_unset=True)

        if "name" in data and data["name"] is not None:
            tenant.name = data["name"].strip()

        if "phone" in data and data["phone"] is not None:
            normalized_phone = normalize_ke_phone(data["phone"])
            if not normalized_phone:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format.",
                )

            existing = (
                db.query(Tenant)
                .filter(Tenant.phone == normalized_phone, Tenant.id != tenant_id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="Phone already registered for another tenant")

            tenant.phone = normalized_phone

        if "email" in data:
            email = _clean_email(data["email"])
            if email:
                existing = (
                    db.query(Tenant)
                    .filter(func.lower(Tenant.email) == email, Tenant.id != tenant_id)
                    .first()
                )
                if existing:
                    raise HTTPException(status_code=409, detail="Email already registered for another tenant")
            tenant.email = email

        if "password" in data:
            tenant.password = hash_password(data["password"]) if data["password"] else None

        if "id_number" in data:
            tenant.id_number = data["id_number"].strip() if data["id_number"] else None

        if "property_id" in data and data["property_id"] is not None:
            tenant.property_id = data["property_id"]

        if "unit_id" in data and data["unit_id"] is not None:
            unit = db.query(Unit).filter(Unit.id == data["unit_id"]).first()
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found")

            if tenant.property_id and unit.property_id != tenant.property_id:
                raise HTTPException(status_code=400, detail="Selected unit does not belong to tenant property")

            tenant.unit_id = data["unit_id"]

        db.commit()
        db.refresh(tenant)
        return tenant

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def delete_tenant(db: Session, tenant_id: int) -> bool:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return False

    try:
        db.delete(tenant)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def assign_existing_tenant_to_unit(
    db: Session,
    tenant: Tenant,
    unit: Unit,
    rent_amount: float,
    start_date: date,
):
    try:
        if int(getattr(unit, "occupied", 0) or 0) == 1:
            raise HTTPException(status_code=409, detail="Unit already occupied")

        active_lease = (
            db.query(Lease)
            .filter(Lease.tenant_id == tenant.id, Lease.active == 1)
            .first()
        )
        if active_lease:
            raise HTTPException(status_code=409, detail="Tenant already has an active lease")

        tenant.property_id = unit.property_id
        tenant.unit_id = unit.id

        lease = Lease(
            tenant_id=tenant.id,
            unit_id=unit.id,
            start_date=start_date,
            end_date=None,
            rent_amount=rent_amount,
            active=1,
        )
        db.add(lease)

        unit.occupied = 1

        db.commit()
        db.refresh(lease)
        db.refresh(tenant)
        return lease

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))