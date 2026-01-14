# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.auth.jwt_utils import decode_access_token

# OAuth2 scheme - expects "Authorization: Bearer <token>"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# -------------------------
# DB Dependency
# -------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# Auth Dependency
# -------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decode JWT and return current user claims.
    """
    try:
        payload = decode_access_token(token)
        return payload  # contains sub (user_id), role, exp
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# -------------------------
# Role-based Access Guard
# -------------------------
def role_required(allowed_roles: list[str]):
    """
    Returns a dependency that ensures the current user has one of the allowed roles.
    Usage:
        @router.get("/secure")
        def secure_endpoint(
            current_user: dict = Depends(role_required(["admin", "landlord"]))
        ):
            ...
    """
    def _role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return _role_checker
