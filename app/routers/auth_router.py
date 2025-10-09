# app/routers/auth_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.models.property_models import Property
from app.schemas.auth_schemas import RegisterUser, LoginUser
from app.auth.utils import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    print("🟢 Received registration data:", data.dict())
    user = None

    try:
        # Enforce password requirement for non-tenant roles
        if data.role != "tenant" and (not data.password or data.password.strip() == ""):
            print("❌ Missing password for role:", data.role)
            raise HTTPException(status_code=400, detail="Password is required for this role")

        # Role-based registration
        if data.role == "landlord":
            print("➡️ Registering landlord...")
            user = Landlord(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        elif data.role == "manager":
            print("➡️ Registering property manager...")
            user = PropertyManager(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        elif data.role == "tenant":
            print("➡️ Registering tenant...")
            if not data.property_code or not data.unit_id:
                print("❌ Tenant missing property_code or unit_id")
                raise HTTPException(
                    status_code=400,
                    detail="Property code and unit are required for tenant registration",
                )

            property_obj = db.query(Property).filter(Property.property_code == data.property_code).first()
            if not property_obj:
                print("❌ Invalid property code:", data.property_code)
                raise HTTPException(status_code=404, detail="Invalid property code")

            user = Tenant(
                name=data.name,
                phone=data.phone,
                email=data.email,
                property_id=property_obj.id,
                unit_id=data.unit_id,
                password=hash_password(data.password) if data.password else None,
            )

        elif data.role == "admin":
            print("➡️ Registering admin...")
            user = Admin(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password),
            )

        else:
            print("❌ Invalid role:", data.role)
            raise HTTPException(status_code=400, detail="Invalid role")

        # Save to DB
        db.add(user)
        db.commit()
        db.refresh(user)

        print("✅ Registration successful for:", data.role, "ID:", user.id)
        return {"message": f"{data.role.capitalize()} registered successfully", "id": user.id}

    except HTTPException as e:
        print(f"⚠️ HTTPException: {e.detail}")
        raise
    except Exception as e:
        print(f"💥 Unexpected error during registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    print("🟢 Login request for:", data.dict())

    user = None
    if data.role == "landlord":
        user = db.query(Landlord).filter(Landlord.phone == data.phone).first()
    elif data.role == "manager":
        user = db.query(PropertyManager).filter(PropertyManager.phone == data.phone).first()
    elif data.role == "tenant":
        user = db.query(Tenant).filter(Tenant.phone == data.phone).first()
    elif data.role == "admin":
        user = db.query(Admin).filter(Admin.phone == data.phone).first()

    if not user:
        print("❌ User not found for role:", data.role)
        raise HTTPException(status_code=404, detail="User not found")

    if data.role != "tenant":
        if not data.password or not verify_password(data.password, user.password):
            print("❌ Invalid password for user:", data.phone)
            raise HTTPException(status_code=401, detail="Invalid password")

    payload = {"sub": str(user.id), "role": data.role}
    token = create_access_token(payload)

    print("✅ Login successful for:", data.role, "ID:", user.id)
    return {"access_token": token, "token_type": "bearer"}
