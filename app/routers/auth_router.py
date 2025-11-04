# app/routers/auth_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from app.dependencies import get_db
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.auth.utils import hash_password, verify_password, create_access_token

# Models are split by domain
from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.models.property_models import Property, Unit, Lease

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    """
    Register a user by role.
    - For tenant: requires property_code and unit_id; creates tenant + ACTIVE lease and marks unit occupied.
    - For other roles: normal create, password required.
    """
    print("🟢 Received registration data:", data.dict())
    user = None

    try:
        if data.role != "tenant" and not data.password:
            raise HTTPException(status_code=400, detail="Password is required for this role")

        if data.role == "landlord":
            print("➡️ Creating landlord...")
            user = Landlord(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        elif data.role == "manager":
            print("➡️ Creating manager...")
            user = PropertyManager(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        elif data.role == "tenant":
            print("➡️ Creating tenant via self-registration...")
            if not data.property_code or not data.unit_id:
                raise HTTPException(status_code=400, detail="Property code and unit are required for tenant registration")

            # 1) Property by code
            prop = db.query(Property).filter(Property.property_code == data.property_code).first()
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            # 2) Unit belongs to that property and is vacant
            unit = (
                db.query(Unit)
                .filter(Unit.id == data.unit_id, Unit.property_id == prop.id)
                .first()
            )
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found for this property")
            if int(unit.occupied or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            # 3) Create tenant row
            user = Tenant(
                name=data.name,
                phone=data.phone,
                email=data.email,
                property_id=prop.id,
                unit_id=unit.id,
                password=hash_password(data.password) if data.password else None,
            )
            db.add(user)
            db.flush()  # get user.id without committing

            # 4) Create ACTIVE lease + mark unit occupied
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

            print(f"✅ Tenant registered, lease={lease.id}, unit occupied")
            return {
                "message": "Tenant registered successfully",
                "id": user.id,
                "lease_id": lease.id,
                "unit_id": unit.id,
                "property_id": prop.id,
            }

        elif data.role == "admin":
            print("➡️ Creating admin...")
            user = Admin(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        else:
            raise HTTPException(status_code=400, detail="Invalid role")

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"✅ {data.role.capitalize()} registered successfully (ID={user.id})")
        return {"message": f"{data.role.capitalize()} registered successfully", "id": user.id}

    except HTTPException as e:
        db.rollback()
        print(f"⚠️ HTTPException: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        print(f"💥 Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    """
    Login by role. Non-tenant requires password; tenant can be passwordless per your flow.
    Returns JWT + user id + role.
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
