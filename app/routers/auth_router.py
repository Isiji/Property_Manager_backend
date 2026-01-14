# app/routers/auth_router.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.password_utils import hash_password, verify_password
from app.auth.jwt_utils import create_access_token
from app.auth.dependencies import get_db
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.utils.phone_utils import normalize_ke_phone

from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.models.property_models import Property, Unit, Lease

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None

def clean_phone(phone: str | None) -> str | None:
    """
    Normalize Kenyan phone numbers to a single format using normalize_ke_phone,
    supporting 07..., 01..., 254..., +254..., and with spaces/dashes.
    """
    if not phone:
        return None
    return normalize_ke_phone(phone)

def exists_by_email_or_phone(db: Session, model, email: str | None, phone: str | None) -> bool:
    conds = []
    if email:
        conds.append(model.email == email)
    if phone:
        conds.append(model.phone == phone)
    if not conds:
        return False
    return db.query(db.query(model.id).filter(or_(*conds)).exists()).scalar()

# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    """
    Register any role.

    Tenants require:
      - property_code
      - unit_number (preferred) OR unit_id
      - password is OPTIONAL for now (because you want passwordless tenant login for now)

    Non-tenant roles:
      - password REQUIRED
    """
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

        # ---------------- MANAGER ----------------
        if role == "manager":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for manager")

            if exists_by_email_or_phone(db, PropertyManager, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a manager")

            user = PropertyManager(
                name=data.name.strip(),
                phone=phone,
                email=email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"message": "Manager registered successfully", "id": user.id}

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
            if not data.property_code or (data.unit_number is None and data.unit_id is None):
                raise HTTPException(
                    status_code=400,
                    detail="Property code and unit (number or id) are required for tenant registration",
                )

            if exists_by_email_or_phone(db, Tenant, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a tenant")

            # ✅ FIX 1: property_code match must be case-insensitive + trimmed
            prop_code = (data.property_code or "").strip()
            prop = (
                db.query(Property)
                .filter(func.upper(func.trim(Property.property_code)) == func.upper(func.trim(prop_code)))
                .first()
            )
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            # ✅ FIX 2: Resolve unit by number (preferred), case-insensitive + trimmed
            if data.unit_number:
                unit_no = (data.unit_number or "").strip()
                unit = (
                    db.query(Unit)
                    .filter(
                        Unit.property_id == prop.id,
                        func.lower(func.trim(Unit.number)) == func.lower(func.trim(unit_no)),
                    )
                    .first()
                )
                if not unit:
                    raise HTTPException(
                        status_code=404,
                        detail=f'Unit "{data.unit_number}" not found for this property',
                    )
            else:
                unit = (
                    db.query(Unit)
                    .filter(Unit.id == data.unit_id, Unit.property_id == prop.id)
                    .first()
                )
                if not unit:
                    raise HTTPException(status_code=404, detail="Unit not found for this property")

            # block if occupied
            if int(getattr(unit, "occupied", 0) or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            # Tenant password is OPTIONAL for now
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
            db.flush()  # get user.id without committing yet

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
    """
    Role-based login:
    - phone is normalized before lookup (supports 07/01 and 254/+254)
    - Landlord/Manager/Admin REQUIRE password
    - Tenant login is PASSWORDLESS for now (phone + role only)
      (Later you should replace this with OTP to be safe)
    """
    role = (data.role or "").strip().lower()
    model_map = {
        "landlord": Landlord,
        "manager": PropertyManager,
        "tenant": Tenant,
        "admin": Admin,
    }
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid role")

    phone = clean_phone(data.phone)
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format."
        )

    user = db.query(model).filter(model.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Tenant passwordless login (temporary)
    if role == "tenant":
        token = create_access_token({"sub": str(user.id), "role": role})
        return {"access_token": token, "token_type": "bearer", "id": user.id, "role": role}

    # Non-tenant roles must verify password
    if not getattr(user, "password", None):
        raise HTTPException(status_code=401, detail="Account has no password set")

    if not data.password or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_access_token({"sub": str(user.id), "role": role})
    return {"access_token": token, "token_type": "bearer", "id": user.id, "role": role}
