#auth_lookup_service.py
from sqlalchemy.orm import Session

from app.models.user_models import Landlord, ManagerUser, Tenant, Admin, SuperAdmin


ROLE_MODEL_MAP = {
    "landlord": Landlord,
    "manager": ManagerUser,
    "tenant": Tenant,
    "admin": Admin,
    "super_admin": SuperAdmin,
}


def get_user_by_role_and_email(db: Session, role: str, email: str):
    role = (role or "").strip().lower()
    model = ROLE_MODEL_MAP.get(role)
    if not model:
        return None, None

    user = db.query(model).filter(model.email == email).first()
    return model, user


def set_user_password(user, hashed_password: str, role: str):
    role = (role or "").strip().lower()

    if role == "manager":
        user.password_hash = hashed_password
    else:
        user.password = hashed_password