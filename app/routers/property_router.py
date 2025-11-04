# app/routers/property_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db
from app.models.property_models import Property, Unit, Lease
from app.models.user_models import Landlord
from app.schemas import property_schema as schemas  # if you have one; otherwise inline Pydantic below

router = APIRouter(prefix="/properties", tags=["Properties"])


# ---- Create (optional: adjust to your existing schema) -----------------------
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_property(payload: dict, db: Session = Depends(get_db)):
    """
    Minimal create; replace `payload: dict` with your Pydantic (e.g., PropertyCreate) if you have it.
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


# ---- Read: list by landlord (used by your LandlordHome) ----------------------
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


# ---- Read: single (basic) ----------------------------------------------------
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


# ---- Read: detailed with units + tenant + lease (for your Units table) ------
@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    """
    Returns the property with a detailed units array:
    - status: 'occupied' | 'vacant' (from unit.occupied)
    - tenant: active lease tenant (name, phone, email), or null
    - lease: active lease info, or null
    """
    prop = (
        db.query(Property)
        .options(
            joinedload(Property.units)
            .joinedload(Unit.lease)
            .joinedload(Lease.tenant)
        )
        .filter(Property.id == property_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    units_out = []
    for u in prop.units:
        lease = u.lease  # uselist=False on your model
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
        "total_units": len(prop.units),
        "occupied_units": sum(1 for x in prop.units if int(x.occupied or 0) == 1),
        "vacant_units": sum(1 for x in prop.units if int(x.occupied or 0) == 0),
        "units": units_out,
    }


# ---- Update (optional minimal) ----------------------------------------------
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


# ---- Delete (optional minimal) ----------------------------------------------
@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(p)
    db.commit()
    return
