from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
)
from app.utils.phone_utils import normalize_ke_phone

# NOTE: adjust these imports to your actual model module paths.
from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.models.property_models import Property, Unit, Lease

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_identity(email: str | None, phone: str | None) -> tuple[str | None, str | None]:
    """
    - Lowercase + trim email
    - Normalize phone to +2547XXXXXXX style
    """
    email_clean = (email or "").strip().lower() or None
    phone_clean = normalize_ke_phone(phone or "") if phone else None
    return email_clean, phone_clean


def _exists_by_email_or_phone(db: Session, model, email: str | None, phone: str | None) -> bool:
    """
    Check if any row in `model` already uses this email or phone.
    """
    q = db.query(model.id)
    conds = []
    if email:
        conds.append(model.email == email)
    if phone:
        conds.append(model.phone == phone)
    if not conds:
        return False
    return db.query(q.filter(or_(*conds)).exists()).scalar()


def get_current_token(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decode JWT from Authorization: Bearer <token> header.
    Uses SECRET_KEY and ALGORITHM from app.auth.utils.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # We expect "sub" (user id) and "role" in payload
        if "sub" not in payload or "role" not in payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    """
    Register any role. For tenants:
      - property_code + (unit_number preferred OR unit_id)
      - Creates active lease and marks unit occupied.

    Returns clean 409 errors for duplicate email/phone instead of 500.
    """
    print("🟢 Received registration data:", data.dict())

    # Password requirement for non-tenants
    if data.role != "tenant" and not data.password:
        raise HTTPException(status_code=400, detail="Password is required for this role")

    try:
        email, phone = _clean_identity(data.email, data.phone)

        # -------------------------------------------------------------------
        # LANDLORD
        # -------------------------------------------------------------------
        if data.role == "landlord":
            if _exists_by_email_or_phone(db, Landlord, email, phone):
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
            print(f"✅ Landlord registered (ID={user.id})")
            return {"message": "Landlord registered successfully", "id": user.id}

        # -------------------------------------------------------------------
        # MANAGER
        # -------------------------------------------------------------------
        if data.role == "manager":
            if _exists_by_email_or_phone(db, PropertyManager, email, phone):
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
            print(f"✅ Manager registered (ID={user.id})")
            return {"message": "Manager registered successfully", "id": user.id}

        # -------------------------------------------------------------------
        # ADMIN
        # -------------------------------------------------------------------
        if data.role == "admin":
            if _exists_by_email_or_phone(db, Admin, email, phone):
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
            print(f"✅ Admin registered (ID={user.id})")
            return {"message": "Admin registered successfully", "id": user.id}

        # -------------------------------------------------------------------
        # TENANT
        # -------------------------------------------------------------------
        if data.role == "tenant":
            # property + (unit_number or unit_id) required
            if not data.property_code or (data.unit_number is None and data.unit_id is None):
                raise HTTPException(
                    status_code=400,
                    detail="Property code and unit (number or id) are required for tenant registration",
                )

            if _exists_by_email_or_phone(db, Tenant, email, phone):
                raise HTTPException(status_code=409, detail="Email or phone already registered for a tenant")

            prop = db.query(Property).filter(Property.property_code == data.property_code).first()
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            # Resolve unit: prefer unit_number if provided
            if data.unit_number:
                unit = (
                    db.query(Unit)
                    .filter(
                        Unit.property_id == prop.id,
                        func.lower(func.trim(Unit.number)) == func.lower(func.trim(data.unit_number)),
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

            # prevent double occupancy
            if int(getattr(unit, "occupied", 0) or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            # create tenant
            user = Tenant(
                name=data.name.strip(),
                phone=phone,
                email=email,
                property_id=prop.id,
                unit_id=unit.id,
                password=hash_password(data.password) if data.password else None,
                id_number=data.id_number,
            )
            db.add(user)
            db.flush()  # get tenant id

            # create active lease + mark unit occupied
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

            print(f"✅ Tenant registered (tenant_id={user.id}, lease_id={lease.id}, unit_id={unit.id})")
            return {
                "message": "Tenant registered successfully",
                "id": user.id,
                "lease_id": lease.id,
                "unit_id": unit.id,
                "property_id": prop.id,
            }

        # Unknown role
        raise HTTPException(status_code=400, detail="Invalid role")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"💥 Registration error: {e}")
        msg = str(e)
        if "UniqueViolation" in msg or "duplicate key value" in msg:
            # fallback if DB error slipped through pre-check
            raise HTTPException(status_code=409, detail="Email or phone already registered")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    """
    Role-based login.
    - Normalizes phone before lookup.
    - Non-tenant roles must have valid password.
    """
    print("🟢 Login request:", data.dict())

    model_map = {
        "landlord": Landlord,
        "manager": PropertyManager,
        "tenant": Tenant,
        "admin": Admin,
    }
    model = model_map.get(data.role)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid role")

    _, phone = _clean_identity(None, data.phone)
    user = db.query(model).filter(model.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role != "tenant":
        if not data.password or not verify_password(data.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid password")

    payload = {"sub": str(user.id), "role": data.role}
    token = create_access_token(payload)
    print(f"✅ Login success for {data.role} (ID={user.id})")
    return {"access_token": token, "token_type": "bearer", "id": user.id, "role": data.role}


@router.get("/profile")
def my_profile(
    db: Session = Depends(get_db),
    token: dict = Depends(get_current_token),
):
    """
    Simple profile endpoint used by the Flutter frontend.
    Reads user id + role from JWT.
    """
    role = token.get("role")
    sub = token.get("sub")

    model_map = {
        "landlord": Landlord,
        "manager": PropertyManager,
        "tenant": Tenant,
        "admin": Admin,
    }
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid role in token")

    row = db.query(model).filter(model.id == int(sub)).first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row.id,
        "name": getattr(row, "name", None),
        "phone": getattr(row, "phone", None),
        "email": getattr(row, "email", None),
        "role": role,
        "id_number": getattr(row, "id_number", None),
    }
