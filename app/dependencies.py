from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.auth.jwt_utils import decode_access_token
from app.models.user_models import Landlord, Tenant, Admin, SuperAdmin, ManagerUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """
    Decode JWT, confirm user exists, and return safe auth context.
    """
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
        "tenant": Tenant,
        "admin": Admin,
        "super_admin": SuperAdmin,
        "manager": ManagerUser,  # IMPORTANT: manager auth is against ManagerUser
    }

    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=401, detail="Unknown role")

    user = db.query(model).filter(model.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Roles with active flag
    if hasattr(user, "active") and getattr(user, "active") is False:
        raise HTTPException(status_code=403, detail="Account is inactive")

    auth_ctx = {
        "id": user.id,
        "sub": str(user.id),
        "role": role,
        "phone": getattr(user, "phone", None),
        "email": getattr(user, "email", None),
        "name": getattr(user, "name", None),
    }

    if role == "manager":
        auth_ctx["manager_id"] = getattr(user, "manager_id", None)
        auth_ctx["staff_role"] = getattr(user, "staff_role", None)

    return auth_ctx


def role_required(allowed_roles: list[str]):
    def _role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current_user
    return _role_checker