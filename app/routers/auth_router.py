from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.password_utils import hash_password, verify_password
from app.auth.jwt_utils import create_access_token
from app.auth.dependencies import get_db
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.utils.phone_utils import normalize_ke_phone

from app.models.user_models import Landlord, PropertyManager, ManagerUser, Tenant, Admin
from app.models.property_models import Property, Unit, Lease

router = APIRouter(prefix="/auth", tags=["Authentication"])


def clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return normalize_ke_phone(phone)


def exists_by_email_or_phone(db: Session, model, email: str | None, phone: str | None) -> bool:
    conds = []
    if hasattr(model, "email") and email:
        conds.append(model.email == email)
    if hasattr(model, "phone") and phone:
        conds.append(model.phone == phone)
    if not conds:
        return False
    return db.query(db.query(model.id).filter(or_(*conds)).exists()).scalar()


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    try:
        email = clean_email(data.email)
        phone = clean_phone(data.phone)

        if not phone:
            raise HTTPException(
                status_code=400,
                detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format."
            )

        role = (data.role or "").strip().lower()

        # ---------------- LANDLORD ----------------
        if role == "landlord":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for landlord")
            if exists_by_email_or_phone(db, Landlord, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a landlord")

            user = Landlord(
                name=data.name.strip(),
                phone=phone,
                email=email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"message": "Landlord registered successfully", "id": user.id}

        # ---------------- MANAGER (ORG + STAFF) ----------------
        if role == "manager":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for manager")

            # Staff phone/email must be unique under ManagerUser
            if exists_by_email_or_phone(db, ManagerUser, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a manager staff")

            manager_type = (data.manager_type or "individual").strip().lower()
            if manager_type not in ("individual", "agency"):
                raise HTTPException(status_code=400, detail="manager_type must be 'individual' or 'agency'")

            company_name = (data.company_name or "").strip() or None
            contact_person = (data.contact_person or "").strip() or None
            office_phone = (data.office_phone or "").strip() or None
            office_email = clean_email(data.office_email)

            if manager_type == "agency" and not company_name:
                raise HTTPException(status_code=400, detail="company_name is required when manager_type='agency'")

            # Org display rule:
            # - agency: show company_name (fallback name)
            # - individual: show name
            org_name = company_name if (manager_type == "agency" and company_name) else data.name.strip()

            org = PropertyManager(
                name=org_name,
                phone=phone,          # keep as a main contact phone (can be staff phone for now)
                email=email,          # can be staff email for now
                password=None,        # moved to ManagerUser
                id_number=data.id_number,

                type=manager_type,
                company_name=company_name,
                contact_person=contact_person if manager_type == "agency" else None,
                office_phone=office_phone if manager_type == "agency" else None,
                office_email=office_email if manager_type == "agency" else None,
                logo_url=None,
            )
            db.add(org)
            db.flush()  # get org.id

            # First staff = admin
            staff_display_name = contact_person if (manager_type == "agency" and contact_person) else data.name.strip()

            staff = ManagerUser(
                manager_id=org.id,
                name=staff_display_name,
                phone=phone,
                email=email,
                password_hash=hash_password(data.password),
                id_number=data.id_number,
                staff_role="manager_admin",
                active=True,
            )
            db.add(staff)

            db.commit()
            db.refresh(org)
            db.refresh(staff)

            return {
                "message": "Manager registered successfully",
                "manager_id": org.id,
                "staff_id": staff.id,
                "manager_type": org.type,
                "manager_name": org.company_name or org.name,
            }

        # ---------------- ADMIN ----------------
        if role == "admin":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for admin")
            if exists_by_email_or_phone(db, Admin, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for an admin")

            user = Admin(
                name=data.name.strip(),
                phone=phone,
                email=email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"message": "Admin registered successfully", "id": user.id}

        # ---------------- TENANT ----------------
        if role == "tenant":
            if not data.property_code:
                raise HTTPException(status_code=400, detail="Property code is required for tenant registration")

            unit_number_in = (data.unit_number or "").strip() if getattr(data, "unit_number", None) else ""
            unit_id_in = getattr(data, "unit_id", None)

            if not unit_number_in and unit_id_in is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unit is required (enter unit name/number or select a unit).",
                )

            if exists_by_email_or_phone(db, Tenant, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a tenant")

            prop_code = (data.property_code or "").strip()
            prop = (
                db.query(Property)
                .filter(func.upper(func.trim(Property.property_code)) == func.upper(func.trim(prop_code)))
                .first()
            )
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            if unit_number_in:
                unit = (
                    db.query(Unit)
                    .filter(
                        Unit.property_id == prop.id,
                        func.lower(func.trim(Unit.number)) == func.lower(func.trim(unit_number_in)),
                    )
                    .first()
                )
                if not unit:
                    raise HTTPException(
                        status_code=404,
                        detail=f'Unit "{unit_number_in}" not found for this property',
                    )
            else:
                unit = (
                    db.query(Unit)
                    .filter(Unit.id == unit_id_in, Unit.property_id == prop.id)
                    .first()
                )
                if not unit:
                    raise HTTPException(status_code=404, detail="Unit not found for this property")

            if int(getattr(unit, "occupied", 0) or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            tenant_password = hash_password(data.password) if data.password else None

            user = Tenant(
                name=data.name.strip(),
                phone=phone,
                email=email,
                property_id=prop.id,
                unit_id=unit.id,
                password=tenant_password,
                id_number=data.id_number,
            )
            db.add(user)
            db.flush()

            rent_amount = float(getattr(unit, "rent_amount", 0) or 0)
            lease = Lease(
                tenant_id=user.id,
                unit_id=unit.id,
                start_date=date.today(),
                end_date=None,
                rent_amount=rent_amount,
                active=1,
            )
            db.add(lease)
            unit.occupied = 1

            db.commit()
            db.refresh(user)
            db.refresh(lease)

            return {
                "message": "Tenant registered successfully",
                "id": user.id,
                "lease_id": lease.id,
                "unit_id": unit.id,
                "property_id": prop.id,
            }

        raise HTTPException(status_code=400, detail="Invalid role")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    role = (data.role or "").strip().lower()

    phone = clean_phone(data.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format.")

    # -------- MANAGER login via ManagerUser --------
    if role == "manager":
        staff = db.query(ManagerUser).filter(ManagerUser.phone == phone, ManagerUser.active == True).first()  # noqa
        if not staff:
            raise HTTPException(status_code=404, detail="User not found")

        if not data.password or not verify_password(data.password, staff.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")

        token = create_access_token({
            "sub": str(staff.id),
            "role": "manager",
            "manager_id": staff.manager_id,
            "staff_role": staff.staff_role,
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "id": staff.id,
            "manager_id": staff.manager_id,
            "role": "manager",
        }

    # -------- others unchanged --------
    model_map = {
        "landlord": Landlord,
        "tenant": Tenant,
        "admin": Admin,
    }
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = db.query(model).filter(model.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if role == "tenant":
        token = create_access_token({"sub": str(user.id), "role": role})
        return {"access_token": token, "token_type": "bearer", "id": user.id, "role": role}

    if not getattr(user, "password", None):
        raise HTTPException(status_code=401, detail="Account has no password set")

    if not data.password or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_access_token({"sub": str(user.id), "role": role})
    return {"access_token": token, "token_type": "bearer", "id": user.id, "role": role}
