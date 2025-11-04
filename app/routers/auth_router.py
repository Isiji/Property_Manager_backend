from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.auth.utils import hash_password, verify_password, create_access_token

# NOTE: adjust these imports to your actual model module paths.
from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.models.property_models import Property, Unit, Lease


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    """
    Register any role. For tenants:
      - Provide property_code and either unit_number (preferred) or unit_id.
      - Creates the tenant, an ACTIVE lease, and marks the unit occupied.
    """
    print("🟢 Received registration data:", data.dict())

    # Password requirement for non-tenants
    if data.role != "tenant" and not data.password:
        raise HTTPException(status_code=400, detail="Password is required for this role")

    try:
        # Landlord
        if data.role == "landlord":
            user = Landlord(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),  # store hashed
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Landlord registered (ID={user.id})")
            return {"message": "Landlord registered successfully", "id": user.id}

        # Manager
        if data.role == "manager":
            user = PropertyManager(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Manager registered (ID={user.id})")
            return {"message": "Manager registered successfully", "id": user.id}

        # Admin
        if data.role == "admin":
            user = Admin(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Admin registered (ID={user.id})")
            return {"message": "Admin registered successfully", "id": user.id}

        # Tenant
        if data.role == "tenant":
            # Guard: property + (unit_number or unit_id) are required
            if not data.property_code or (data.unit_number is None and data.unit_id is None):
                raise HTTPException(
                    status_code=400,
                    detail="Property code and unit (number or id) are required for tenant registration",
                )

            # Resolve property by code
            prop = db.query(Property).filter(Property.property_code == data.property_code).first()
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            # Prefer unit_number if provided (case-insensitive, trimmed, scoped to property)
            unit = None
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

            # Prevent double-occupancy
            if int(getattr(unit, "occupied", 0) or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            # Create tenant
            user = Tenant(
                name=data.name,
                phone=data.phone,
                email=data.email,
                property_id=prop.id,
                unit_id=unit.id,
                password=hash_password(data.password) if data.password else None,
                id_number=data.id_number,
            )
            db.add(user)
            db.flush()  # get user.id

            # Create ACTIVE lease and mark unit occupied
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    """
    Role-based login.
    - Tenant can be passwordless (if you allow it).
    - Others must supply a valid password.
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

    user = db.query(model).filter(model.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role != "tenant":
        if not data.password or not verify_password(data.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid password")

    payload = {"sub": str(user.id), "role": data.role}
    token = create_access_token(payload)

    print(f"✅ Login success for {data.role} (ID={user.id})")
    return {"access_token": token, "token_type": "bearer", "id": user.id, "role": data.role}
