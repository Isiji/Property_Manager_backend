from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user_models import Landlord, PropertyManager, Tenant, Admin
from app.auth.jwt_utils import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    model_map = {
        "landlord": Landlord,
        "manager": PropertyManager,
        "tenant": Tenant,
        "admin": Admin,
    }
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=401, detail="Unknown role")

    user = db.query(model).filter(model.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {"id": user.id, "role": role, "phone": getattr(user, "phone", None)}

def role_required(allowed_roles: list[str]):
    def wrapper(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current_user
    return wrapper
