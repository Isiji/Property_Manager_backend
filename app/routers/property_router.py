from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from jose import jwt, JWTError
from pydantic import BaseModel

from app.auth.dependencies import get_db
from app.auth.jwt_utils import SECRET_KEY, ALGORITHM

from app.models.property_models import Property, Unit, Lease
from app.models.user_models import Landlord, PropertyManager
from app.models.agency_models import PropertyAgentAssignment, PropertyExternalManagerAssignment

router = APIRouter(prefix="/properties", tags=["Properties"])
bearer = HTTPBearer(auto_error=False)


def _decode(creds: HTTPAuthorizationCredentials) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ✅ IMPORTANT: /me MUST be above /{property_id}
@router.get("/me")
def properties_visible_to_me(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    """
    Returns properties the logged-in manager staff can access.

    Visibility rules:
    A) Properties owned by my org: Property.manager_id == my manager_id
    B) Properties assigned to me (internal staff assignment)
    C) Properties assigned to my org as an external agent (external assignment)
    """
    payload = _decode(creds)
    if payload.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Not a manager session")

    staff_id = int(payload.get("sub"))
    manager_id = int(payload.get("manager_id"))

    # A) org-managed
    q_org = db.query(Property.id).filter(Property.manager_id == manager_id)

    # B) staff assignments
    q_staff = (
        db.query(Property.id)
        .join(PropertyAgentAssignment, PropertyAgentAssignment.property_id == Property.id)
        .filter(
            PropertyAgentAssignment.assignee_user_id == staff_id,
            PropertyAgentAssignment.active == True,  # noqa
        )
    )

    # C) external manager assignment (org-level)
    q_ext = (
        db.query(Property.id)
        .join(PropertyExternalManagerAssignment, PropertyExternalManagerAssignment.property_id == Property.id)
        .filter(
            PropertyExternalManagerAssignment.agent_manager_id == manager_id,
            PropertyExternalManagerAssignment.active == True,  # noqa
        )
    )

    ids = set([r[0] for r in q_org.all()] + [r[0] for r in q_staff.all()] + [r[0] for r in q_ext.all()])
    if not ids:
        return []

    rows = db.query(Property).filter(Property.id.in_(list(ids))).order_by(Property.id.desc()).all()

    return [
        {
            "id": p.id,
            "name": getattr(p, "name", None),
            "address": getattr(p, "address", None),
            "property_code": getattr(p, "property_code", None),
            "manager_id": getattr(p, "manager_id", None),
            "landlord_id": getattr(p, "landlord_id", None),
        }
        for p in rows
    ]


# ---- Create ---------------------------------------------------------------
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_property(payload: dict, db: Session = Depends(get_db)):
    """
    Expected keys: name, address, landlord_id, (optional) manager_id
    """
    name = (payload.get("name") or "").strip()
    address = (payload.get("address") or "").strip()
    landlord_id = payload.get("landlord_id")
    manager_id = payload.get("manager_id")

    if not name or not address or not landlord_id:
        raise HTTPException(status_code=400, detail="name, address, landlord_id required")

    ll = db.query(Landlord).filter(Landlord.id == landlord_id).first()
    if not ll:
        raise HTTPException(status_code=404, detail="Landlord not found")

    if manager_id is not None:
        mgr = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
        if not mgr:
            raise HTTPException(status_code=404, detail="Property Manager not found")

    p = Property(name=name, address=address, landlord_id=landlord_id, manager_id=manager_id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "address": p.address,
        "property_code": p.property_code,
        "landlord_id": p.landlord_id,
        "manager_id": p.manager_id,
    }


# ---- Read: list by landlord ----------------------------------------------
@router.get("/landlord/{landlord_id}")
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Property)
        .filter(Property.landlord_id == landlord_id)
        .order_by(Property.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "address": r.address,
            "property_code": r.property_code,
            "landlord_id": r.landlord_id,
            "manager_id": r.manager_id,
        }
        for r in rows
    ]


# ---- Read: assigned property manager --------------------------------------
@router.get("/{property_id}/property-manager")
def get_assigned_property_manager(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if not prop.manager_id:
        return None

    mgr = db.query(PropertyManager).filter(PropertyManager.id == prop.manager_id).first()
    if not mgr:
        return None

    return {
        "id": mgr.id,
        "name": mgr.name,
        "phone": mgr.phone,
        "email": mgr.email,
        "id_number": getattr(mgr, "id_number", None),
    }


# ---- Read: detailed with units + tenant + lease ---------------------------
@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    prop = (
        db.query(Property)
        .options(
            joinedload(Property.units)
            .joinedload(Unit.lease)
            .joinedload(Lease.tenant),
            joinedload(Property.landlord),
        )
        .filter(Property.id == property_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    landlord_obj = None
    ll = getattr(prop, "landlord", None)
    if ll:
        landlord_obj = {
            "id": ll.id,
            "name": ll.name,
            "phone": getattr(ll, "phone", None),
            "email": getattr(ll, "email", None),
            "id_number": getattr(ll, "id_number", None),
        }

    units_out = []
    for u in prop.units:
        lease = u.lease
        active = (lease is not None) and int(lease.active or 0) == 1
        tenant = lease.tenant if active else None

        units_out.append({
            "id": u.id,
            "number": u.number,
            "rent_amount": str(u.rent_amount) if u.rent_amount is not None else None,
            "property_id": u.property_id,
            "status": "occupied" if int(u.occupied or 0) == 1 else "vacant",
            "tenant": None if not tenant else {
                "id": tenant.id,
                "name": tenant.name,
                "phone": tenant.phone,
                "email": tenant.email,
                "id_number": getattr(tenant, "id_number", None),
            },
            "lease": None if not lease else {
                "id": lease.id,
                "start_date": lease.start_date.isoformat() if lease.start_date else None,
                "end_date": lease.end_date.isoformat() if lease.end_date else None,
                "rent_amount": float(lease.rent_amount or 0),
                "active": int(lease.active or 0),
            },
        })

    return {
        "id": prop.id,
        "name": prop.name,
        "address": prop.address,
        "property_code": prop.property_code,
        "landlord_id": prop.landlord_id,
        "manager_id": prop.manager_id,
        "landlord": landlord_obj,
        "total_units": len(prop.units),
        "occupied_units": sum(1 for x in prop.units if int(x.occupied or 0) == 1),
        "vacant_units": sum(1 for x in prop.units if int(x.occupied or 0) == 0),
        "units": units_out,
    }


# ---- Read: single (basic) -------------------------------------------------
@router.get("/{property_id}")
def get_property(property_id: int, db: Session = Depends(get_db)):
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "id": p.id,
        "name": p.name,
        "address": p.address,
        "property_code": p.property_code,
        "landlord_id": p.landlord_id,
        "manager_id": p.manager_id,
    }


# ---- Update ---------------------------------------------------------------
@router.put("/{property_id}")
def update_property(property_id: int, payload: dict, db: Session = Depends(get_db)):
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")

    name = payload.get("name")
    address = payload.get("address")
    manager_id = payload.get("manager_id")

    if name is not None:
        p.name = name.strip() or p.name
    if address is not None:
        p.address = address.strip() or p.address
    if manager_id is not None:
        p.manager_id = manager_id

    db.commit()
    db.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "address": p.address,
        "property_code": p.property_code,
        "landlord_id": p.landlord_id,
        "manager_id": p.manager_id,
    }


# ---- Delete ---------------------------------------------------------------
@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(p)
    db.commit()
    return


class AssignManagerPayload(BaseModel):
    manager_id: int | None = None


@router.get("/manager/{manager_id}")
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Property)
        .filter(Property.manager_id == manager_id)
        .order_by(Property.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "address": r.address,
            "property_code": r.property_code,
            "landlord_id": r.landlord_id,
            "manager_id": r.manager_id,
        }
        for r in rows
    ]


@router.put("/{property_id}/assign-manager")
def assign_manager(property_id: int, payload: AssignManagerPayload, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if payload.manager_id is not None:
        mgr = db.query(PropertyManager).filter(PropertyManager.id == payload.manager_id).first()
        if not mgr:
            raise HTTPException(status_code=404, detail="Property Manager not found")

    prop.manager_id = payload.manager_id
    db.commit()
    db.refresh(prop)

    return {
        "message": "Property manager assignment updated",
        "property_id": prop.id,
        "manager_id": prop.manager_id,
    }
