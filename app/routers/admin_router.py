from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, role_required
from app.auth.password_utils import hash_password
from app.models.user_models import Admin
from app.models.audit_log_model import AuditLog
from app.utils.phone_utils import normalize_ke_phone

router = APIRouter(
    prefix="/admins",
    tags=["Admins"],
)


# -----------------------------
# Local schemas
# -----------------------------
class AdminCreate(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    id_number: Optional[str] = None


class AdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    id_number: Optional[str] = None
    active: Optional[bool] = None


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    id_number: Optional[str] = None
    active: bool


# -----------------------------
# Helpers
# -----------------------------
def clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return normalize_ke_phone(phone)


def log_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None,
    actor_role: str | None,
    actor_id: int | None,
    message: str | None = None,
):
    db.add(
        AuditLog(
            property_id=None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_role=actor_role,
            actor_id=actor_id,
            message=message,
        )
    )


def ensure_unique_admin(db: Session, *, email: str | None, phone: str | None, exclude_id: int | None = None):
    q = db.query(Admin)
    conds = []
    if email:
        conds.append(Admin.email == email)
    if phone:
        conds.append(Admin.phone == phone)

    if not conds:
        return

    q = q.filter(or_(*conds))
    if exclude_id is not None:
        q = q.filter(Admin.id != exclude_id)

    existing = q.first()
    if existing:
        raise HTTPException(status_code=409, detail="Admin with this email or phone already exists")


# -----------------------------
# Routes
# -----------------------------
@router.post(
    "/",
    response_model=AdminOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(role_required(["super_admin"]))],
)
def create_admin(
    payload: AdminCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    email = clean_email(payload.email)
    phone = clean_phone(payload.phone)

    if not email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if not phone:
        raise HTTPException(status_code=400, detail="Valid phone is required")
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")

    ensure_unique_admin(db, email=email, phone=phone)

    admin = Admin(
        name=payload.name.strip(),
        email=email,
        phone=phone,
        password=hash_password(payload.password),
        id_number=payload.id_number,
        active=True,
    )
    db.add(admin)
    db.flush()

    log_audit(
        db,
        action="CREATE_ADMIN",
        entity_type="admin",
        entity_id=admin.id,
        actor_role=current_user.get("role"),
        actor_id=int(current_user.get("id")),
        message=f"Super admin created admin '{admin.name}'",
    )

    db.commit()
    db.refresh(admin)
    return admin


@router.get(
    "/",
    response_model=List[AdminOut],
    dependencies=[Depends(role_required(["super_admin"]))],
)
def list_admins(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return db.query(Admin).order_by(Admin.id.desc()).offset(skip).limit(limit).all()


@router.get("/{admin_id}", response_model=AdminOut)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role")
    sub = current_user.get("sub")

    if role not in {"super_admin", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to view this admin")

    if role == "admin" and int(sub) != int(admin_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this admin")

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return admin


@router.put("/{admin_id}", response_model=AdminOut)
def update_admin(
    admin_id: int,
    payload: AdminUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role")
    sub = current_user.get("sub")

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if role not in {"super_admin", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to update this admin")

    if role == "admin" and int(sub) != int(admin_id):
        raise HTTPException(status_code=403, detail="Not authorized to update this admin")

    data = payload.model_dump(exclude_unset=True)

    if "email" in data:
        data["email"] = clean_email(data["email"])
        if not data["email"]:
            raise HTTPException(status_code=400, detail="Valid email is required")

    if "phone" in data:
        data["phone"] = clean_phone(data["phone"])
        if not data["phone"]:
            raise HTTPException(status_code=400, detail="Valid phone is required")

    ensure_unique_admin(
        db,
        email=data.get("email"),
        phone=data.get("phone"),
        exclude_id=admin_id,
    )

    # regular admin cannot flip active status
    if role != "super_admin":
        data.pop("active", None)

    if "password" in data:
        pwd = data.pop("password")
        if pwd:
            admin.password = hash_password(pwd)

    for key, value in data.items():
        setattr(admin, key, value)

    log_audit(
        db,
        action="UPDATE_ADMIN",
        entity_type="admin",
        entity_id=admin.id,
        actor_role=current_user.get("role"),
        actor_id=int(current_user.get("id")),
        message=f"{current_user.get('role')} updated admin '{admin.name}'",
    )

    db.commit()
    db.refresh(admin)
    return admin


@router.patch(
    "/{admin_id}/deactivate",
    response_model=AdminOut,
    dependencies=[Depends(role_required(["super_admin"]))],
)
def deactivate_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    admin.active = False

    log_audit(
        db,
        action="DEACTIVATE_ADMIN",
        entity_type="admin",
        entity_id=admin.id,
        actor_role=current_user.get("role"),
        actor_id=int(current_user.get("id")),
        message=f"Super admin deactivated admin '{admin.name}'",
    )

    db.commit()
    db.refresh(admin)
    return admin


@router.patch(
    "/{admin_id}/activate",
    response_model=AdminOut,
    dependencies=[Depends(role_required(["super_admin"]))],
)
def activate_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    admin.active = True

    log_audit(
        db,
        action="ACTIVATE_ADMIN",
        entity_type="admin",
        entity_id=admin.id,
        actor_role=current_user.get("role"),
        actor_id=int(current_user.get("id")),
        message=f"Super admin activated admin '{admin.name}'",
    )

    db.commit()
    db.refresh(admin)
    return admin


@router.delete(
    "/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(role_required(["super_admin"]))],
)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    log_audit(
        db,
        action="DELETE_ADMIN",
        entity_type="admin",
        entity_id=admin.id,
        actor_role=current_user.get("role"),
        actor_id=int(current_user.get("id")),
        message=f"Super admin deleted admin '{admin.name}'",
    )

    db.delete(admin)
    db.commit()
    return None