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
        if data.role != "tenant" and not data.password:
            raise HTTPException(status_code=400, detail="Password is required for this role")

        if data.role == "landlord":
            print("➡️ Creating landlord...")
            user = Landlord(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password)
            )

        elif data.role == "manager":
            print("➡️ Creating manager...")
            user = PropertyManager(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password)
            )

        elif data.role == "tenant":
            print("➡️ Creating tenant...")
            if not data.property_code or not data.unit_id:
                raise HTTPException(status_code=400, detail="Property code and unit are required for tenant registration")

            property_obj = db.query(Property).filter(Property.property_code == data.property_code).first()
            if not property_obj:
                raise HTTPException(status_code=404, detail="Invalid property code")

            user = Tenant(
                name=data.name,
                phone=data.phone,
                email=data.email,
                property_id=property_obj.id,
                unit_id=data.unit_id,
                password=hash_password(data.password) if data.password else None
            )

        elif data.role == "admin":
            print("➡️ Creating admin...")
            user = Admin(
                name=data.name,
                phone=data.phone,
                email=data.email,
                password=hash_password(data.password)
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
    print("🟢 Login request:", data.dict())

    model_map = {
        "landlord": Landlord,
        "manager": PropertyManager,
        "tenant": Tenant,
        "admin": Admin
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
