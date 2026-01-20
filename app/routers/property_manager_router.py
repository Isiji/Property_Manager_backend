from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from jose import jwt, JWTError

from app.auth.dependencies import get_db
from app.schemas.property_manager_schema import (
    PropertyManagerCreate,
    PropertyManagerUpdate,
    PropertyManagerOut,
)
from app.models.user_models import PropertyManager, ManagerUser
from app.auth.password_utils import hash_password
from app.utils.phone_utils import normalize_ke_phone

# IMPORTANT: set this to match your jwt_utils secret/algorithm
from app.auth.jwt_utils import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/managers", tags=["Property Managers"])
bearer = HTTPBearer(auto_error=False)


def _clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def _clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return normalize_ke_phone(phone)


def _exists_by_email_or_phone(db: Session, email: str | None, phone: str | None) -> bool:
    conds = []
    if email:
        conds.append(PropertyManager.email == email)
    if phone:
        conds.append(PropertyManager.phone == phone)
    if not conds:
        return False
    return db.query(db.query(PropertyManager.id).filter(or_(*conds)).exists()).scalar()


def _decode_token(creds: Optional[HTTPAuthorizationCredentials]) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me")
def manager_me(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode_token(creds)
    role = payload.get("role")
    if role != "manager":
        raise HTTPException(status_code=403, detail="Not a manager session")

    staff_id = int(payload.get("sub"))
    manager_id = int(payload.get("manager_id"))

    staff = db.query(ManagerUser).filter(ManagerUser.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Manager staff not found")

    org = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Manager org not found")

    # Display rule: agency => company_name fallback name; individual => name
    manager_name = None
    if org.type == "agency":
        manager_name = (org.company_name or "").strip() or org.name
    else:
        manager_name = org.name

    return {
        "manager_user_id": staff.id,
        "manager_id": org.id,
        "display_name": staff.name,
        "manager_type": org.type,
        "manager_name": manager_name,
        "staff_role": staff.staff_role,
        "staff_phone": staff.phone,
    }


@router.post("/", response_model=PropertyManagerOut, status_code=status.HTTP_201_CREATED)
def create_property_manager(payload: PropertyManagerCreate, db: Session = Depends(get_db)):
    """
    Creates a manager org AND creates the first staff user account.
    - For individual managers: type defaults to "individual"
    - For agencies: type="agency", company_name can be set
    """
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    phone = _clean_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid Kenyan phone number")

    email = _clean_email(getattr(payload, "email", None))
    password = getattr(payload, "password", None)

    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    # Staff uniqueness (login identity)
    staff_email = email
    staff_phone = phone
    if db.query(ManagerUser).filter(ManagerUser.phone == staff_phone).first():
        raise HTTPException(status_code=409, detail="Phone already registered for a manager staff")
    if staff_email and db.query(ManagerUser).filter(ManagerUser.email == staff_email).first():
        raise HTTPException(status_code=409, detail="Email already registered for a manager staff")

    org_type = (getattr(payload, "type", None) or "individual").strip().lower()
    if org_type not in ("individual", "agency"):
        raise HTTPException(status_code=400, detail="type must be individual or agency")

    org = PropertyManager(
        name=name,
        phone=phone,
        email=email,
        password=None,
        id_number=getattr(payload, "id_number", None),
        type=org_type,
        company_name=getattr(payload, "company_name", None),
        contact_person=getattr(payload, "contact_person", None),
        office_phone=getattr(payload, "office_phone", None),
        office_email=getattr(payload, "office_email", None),
        logo_url=getattr(payload, "logo_url", None),
    )

    db.add(org)
    db.flush()

    staff = ManagerUser(
        manager_id=org.id,
        name=name,
        phone=phone,
        email=email,
        password_hash=hash_password(password),
        id_number=getattr(payload, "id_number", None),
        staff_role="manager_admin",
    )
    db.add(staff)

    db.commit()
    db.refresh(org)
    return org


@router.get("/", response_model=List[PropertyManagerOut])
def list_property_managers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(PropertyManager)
        .order_by(PropertyManager.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/search", response_model=List[PropertyManagerOut])
def search_property_managers(q: str, db: Session = Depends(get_db), limit: int = 25):
    query = (q or "").strip()
    if not query:
        return []

    phone_guess = None
    try:
        phone_guess = normalize_ke_phone(query)
    except Exception:
        phone_guess = None

    conds = [
        PropertyManager.name.ilike(f"%{query}%"),
        PropertyManager.email.ilike(f"%{query}%"),
        PropertyManager.phone.ilike(f"%{query}%"),
        PropertyManager.company_name.ilike(f"%{query}%"),
        PropertyManager.office_phone.ilike(f"%{query}%"),
        PropertyManager.office_email.ilike(f"%{query}%"),
    ]
    if phone_guess:
        conds.append(PropertyManager.phone == phone_guess)

    return (
        db.query(PropertyManager)
        .filter(or_(*conds))
        .order_by(PropertyManager.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/{manager_id}", response_model=PropertyManagerOut)
def get_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")
    return manager


@router.put("/{manager_id}", response_model=PropertyManagerOut)
def update_property_manager(manager_id: int, payload: PropertyManagerUpdate, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")

    data = payload.dict(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        manager.name = data["name"].strip() or manager.name

    if "email" in data:
        manager.email = _clean_email(data.get("email"))

    if "phone" in data and data["phone"] is not None:
        phone = _clean_phone(data["phone"])
        if not phone:
            raise HTTPException(status_code=400, detail="Invalid Kenyan phone number")
        manager.phone = phone

    # org fields
    for f in ["type", "company_name", "contact_person", "office_phone", "office_email", "logo_url", "id_number"]:
        if f in data:
            setattr(manager, f, data.get(f))

    # IMPORTANT: password is no longer on org. ignore payload.password if present.

    db.commit()
    db.refresh(manager)
    return manager


@router.delete("/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")

    db.delete(manager)
    db.commit()
    return None
