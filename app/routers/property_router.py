from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app import schemas, models
from app.dependencies import get_db

# ✅ import the concrete CRUD module directly (don’t go through app.crud)
from app.crud import property_crud as pcrud

router = APIRouter(prefix="/properties", tags=["Properties"])

# -------------------------------
# CRUD
# -------------------------------
@router.post("/", response_model=schemas.PropertyOut)
def create_property(payload: schemas.PropertyCreate, db: Session = Depends(get_db)):
    try:
        return pcrud.create_property(db, payload)
    except Exception as e:
        import traceback
        print("❌ ERROR inside create_property route:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[schemas.PropertyOut])
def list_properties(db: Session = Depends(get_db)):
    return pcrud.get_properties(db)

@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = pcrud.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(property_id: int, payload: schemas.PropertyUpdate, db: Session = Depends(get_db)):
    prop = pcrud.update_property(db, property_id, payload)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.delete("/{property_id}", response_model=schemas.PropertyOut)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    prop = pcrud.delete_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

# -------------------------------
# Helper: properties by landlord
# Returns normalized JSON (no raw datetimes)
# -------------------------------
@router.get("/landlord/{landlord_id}")
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    props = pcrud.get_properties_by_landlord(db, landlord_id)
    result = []
    for p in props:
        units_payload = []
        for u in p.units:
            # determine occupancy via flag or active lease
            active_lease = (
                db.query(models.Lease)
                .filter(models.Lease.unit_id == u.id, models.Lease.active == 1)
                .first()
            )
            is_occupied = (u.occupied == 1) or (active_lease is not None)

            tenant_payload = None
            if active_lease and active_lease.tenant:
                t = active_lease.tenant
                tenant_payload = {
                    "id": t.id,
                    "name": t.name,
                    "phone": t.phone,
                    "email": t.email,
                }

            units_payload.append({
                "id": u.id,
                "number": u.number,
                "rent_amount": float(u.rent_amount),
                "property_id": u.property_id,
                "occupied": 1 if is_occupied else 0,
                "status": "occupied" if is_occupied else "vacant",
                "tenant": tenant_payload,  # may be null
            })

        result.append({
            "id": p.id,
            "name": p.name,
            "address": p.address,
            "property_code": p.property_code,
            "landlord_id": p.landlord_id,
            "manager_id": p.manager_id,
            "units": units_payload,
        })

    print("🧾 /properties/landlord payload:", result)
    return result

# -------------------------------
# Helper: properties by manager
# -------------------------------
@router.get("/manager/{manager_id}", response_model=List[schemas.PropertyOut])
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    return pcrud.get_properties_by_manager(db, manager_id)

# -------------------------------
# Detailed view with units + tenant/lease summary
# Normalized fields; ISO datetimes inside nested lease only
# -------------------------------
@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    prop = pcrud.get_property_with_units(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    units_data = []
    occupied_count = 0
    vacant_count = 0

    for u in prop.units:
        active_lease = (
            db.query(models.Lease)
            .filter(models.Lease.unit_id == u.id, models.Lease.active == 1)
            .first()
        )

        is_occupied = (u.occupied == 1) or (active_lease is not None)
        status = "occupied" if is_occupied else "vacant"
        if is_occupied:
            occupied_count += 1
        else:
            vacant_count += 1

        tenant_payload: Optional[dict] = None
        if active_lease and active_lease.tenant:
            t = active_lease.tenant
            tenant_payload = {
                "id": t.id,
                "name": t.name,
                "phone": t.phone,
                "email": t.email,
            }

        lease_payload: Optional[dict] = None
        if active_lease:
            lease_payload = {
                "id": active_lease.id,
                "start_date": active_lease.start_date.isoformat() if active_lease.start_date else None,
                "end_date": active_lease.end_date.isoformat() if active_lease.end_date else None,
                "rent_amount": float(active_lease.rent_amount) if active_lease.rent_amount is not None else None,
                "active": active_lease.active,
            }

        units_data.append({
            "id": u.id,
            "number": u.number,
            "rent_amount": float(u.rent_amount),
            "occupied": u.occupied,
            "status": status,
            "tenant": tenant_payload,
            "lease": lease_payload,
        })

    payload = {
        "id": prop.id,
        "name": prop.name,
        "address": prop.address,
        "property_code": prop.property_code,
        "total_units": len(prop.units),
        "occupied_units": occupied_count,
        "vacant_units": vacant_count,
        "units": units_data,
    }
    print(f"🧾 /properties/{property_id}/with-units-detailed payload:", payload)
    return payload
