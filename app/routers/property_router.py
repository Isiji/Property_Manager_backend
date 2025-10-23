from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app import crud, schemas, models
from app.dependencies import get_db
from app.crud import property_crud


router = APIRouter(prefix="/properties", tags=["Properties"])


# ---------------------------
# Helpers
# ---------------------------

def _to_iso_date(d: Optional[datetime | date]) -> Optional[str]:
    """
    Convert datetime/date to simple 'YYYY-MM-DD' string or None.
    Ensures FastAPI doesn't complain when schema expects a date.
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return None


def _unit_status(u: models.Unit) -> str:
    """
    Normalize unit status from boolean-ish occupied flag.
    """
    return "occupied" if (getattr(u, "occupied", 0) == 1) else "vacant"


def _unit_dict(db: Session, u: models.Unit) -> dict:
    """
    Build a safe dict for a unit row, including tenant & active lease summary.
    """
    # Get active lease (if any)
    active_lease = (
        db.query(models.Lease)
        .filter(models.Lease.unit_id == u.id, models.Lease.active == 1)
        .first()
    )

    # Try to get tenant via lease (preferred), else via relationship (if present)
    tenant_payload = None
    if active_lease and active_lease.tenant:
        t = active_lease.tenant
        tenant_payload = {
            "id": t.id,
            "name": t.name,
            "phone": t.phone,
            "email": t.email,
        }
    elif hasattr(u, "tenant") and u.tenant:
        t = u.tenant
        tenant_payload = {
            "id": t.id,
            "name": t.name,
            "phone": t.phone,
            "email": t.email,
        }

    lease_payload = None
    if active_lease:
        lease_payload = {
            "id": active_lease.id,
            "start_date": _to_iso_date(active_lease.start_date),
            "end_date": _to_iso_date(active_lease.end_date),
            "rent_amount": str(active_lease.rent_amount) if active_lease.rent_amount is not None else None,
            "active": active_lease.active,
        }

    return {
        "id": u.id,
        "number": u.number,
        "rent_amount": str(u.rent_amount),
        "property_id": u.property_id,
        "status": _unit_status(u),  # "occupied" | "vacant"
        "tenant": tenant_payload,
        "lease": lease_payload,
    }


def _property_with_units_payload(db: Session, prop: models.Property) -> dict:
    units_data = []
    occupied_count = 0
    for u in prop.units:
        u_dict = _unit_dict(db, u)
        units_data.append(u_dict)
        if u_dict["status"] == "occupied":
            occupied_count += 1

    total_units = len(prop.units)
    vacant_count = total_units - occupied_count

    return {
        "id": prop.id,
        "name": prop.name,
        "address": prop.address,
        "property_code": prop.property_code,  # make sure this exists on your model
        "total_units": total_units,
        "occupied_units": occupied_count,
        "vacant_units": vacant_count,
        "units": units_data,
    }


# ---------------------------
# CRUD
# ---------------------------

@router.post("/", response_model=schemas.PropertyOut)
def create_property(payload: schemas.PropertyCreate, db: Session = Depends(get_db)):
    try:
        return crud.property_crud.create_property(db, payload)
    except Exception as e:
        import traceback
        print("❌ ERROR inside create_property route:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[schemas.PropertyOut])
def list_properties(db: Session = Depends(get_db)):
    return crud.property_crud.get_properties(db)


@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property_crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(property_id: int, payload: schemas.PropertyUpdate, db: Session = Depends(get_db)):
    prop = crud.property_crud.update_property(db, property_id, payload)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.delete("/{property_id}", response_model=schemas.PropertyOut)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property_crud.delete_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


# ---------------------------
# Helpers / Aggregates
# ---------------------------

@router.get("/landlord/{landlord_id}")
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    """
    Return landlord properties with a safe structure (dates normalized),
    so the frontend can show property cards and unit rows without schema
    date/datetime validation errors.
    """
    props = crud.property_crud.get_properties_by_landlord(db, landlord_id)
    out = []
    for p in props:
        out.append(_property_with_units_payload(db, p))
    return out


@router.get("/manager/{manager_id}", response_model=List[schemas.PropertyOut])
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    return crud.property_crud.get_properties_by_manager(db, manager_id)


@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property_crud.get_property_with_units(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    return _property_with_units_payload(db, prop)
