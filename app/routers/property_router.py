# app/routers/property_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import traceback

from app import models, schemas
from app.dependencies import get_db
from app.crud import property_crud

router = APIRouter(prefix="/properties", tags=["Properties"])

# ------------------------------------------------------------------
# Create Property
# ------------------------------------------------------------------
@router.post("/", response_model=schemas.PropertyOut)
def create_property(payload: schemas.PropertyCreate, db: Session = Depends(get_db)):
    try:
        return property_crud.create_property(db, payload)
    except Exception as e:
        print("❌ ERROR inside create_property route:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------
# List Properties
# ------------------------------------------------------------------
@router.get("/", response_model=List[schemas.PropertyOut])
def list_properties(db: Session = Depends(get_db)):
    return property_crud.get_properties(db)

# ------------------------------------------------------------------
# Get Single Property
# ------------------------------------------------------------------
@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = property_crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

# ------------------------------------------------------------------
# Update Property
# ------------------------------------------------------------------
@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(property_id: int, payload: schemas.PropertyUpdate, db: Session = Depends(get_db)):
    prop = property_crud.update_property(db, property_id, payload)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

# ------------------------------------------------------------------
# Delete Property
# ------------------------------------------------------------------
@router.delete("/{property_id}", response_model=schemas.PropertyOut)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    prop = property_crud.delete_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

# ------------------------------------------------------------------
# Helpers / Filters
# ------------------------------------------------------------------
@router.get("/landlord/{landlord_id}", response_model=List[schemas.PropertyOut])
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    return property_crud.get_properties_by_landlord(db, landlord_id)

@router.get("/manager/{manager_id}", response_model=List[schemas.PropertyOut])
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    return property_crud.get_properties_by_manager(db, manager_id)

# ------------------------------------------------------------------
# Property + Units (detailed view)
# ------------------------------------------------------------------
@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    """
    Returns a detailed object:

    {
      "id": ...,
      "name": "...",
      "address": "...",
      "total_units": N,
      "occupied_units": M,
      "vacant_units": K,
      "units": [
        {
          "id": ...,
          "number": "...",
          "rent_amount": "....",
          "status": "occupied" | "vacant",
          "tenant": { "id": ..., "name": "...", "phone": "...", "email": "..." } | null,
          "lease": { "id": ..., "start_date": ..., "end_date": ..., "rent_amount": "...", "active": 0|1 } | null
        },
        ...
      ]
    }
    """
    try:
        prop = property_crud.get_property_with_units(db, property_id)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        units_data = []
        occupied_count = 0
        vacant_count = 0

        for u in prop.units:
            # derive status from `occupied` (0/1)
            is_occupied = (u.occupied == 1) or (u.occupied is True)
            status = "occupied" if is_occupied else "vacant"
            if is_occupied:
                occupied_count += 1
            else:
                vacant_count += 1

            # Prefer relationship if present (Unit.lease is uselist=False)
            active_lease = None
            if getattr(u, "lease", None) and getattr(u.lease, "active", 0) == 1:
                active_lease = u.lease
            else:
                # fallback query, in case relationship isn't loaded
                active_lease = (
                    db.query(models.Lease)
                    .filter(models.Lease.unit_id == u.id, models.Lease.active == 1)
                    .first()
                )

            # tenant comes from the active lease (if any)
            tenant_info = None
            if active_lease and getattr(active_lease, "tenant", None):
                t = active_lease.tenant
                tenant_info = {
                    "id": t.id,
                    "name": t.name,
                    "phone": t.phone,
                    "email": t.email,
                }

            lease_info = None
            if active_lease:
                lease_info = {
                    "id": active_lease.id,
                    "start_date": active_lease.start_date,
                    "end_date": active_lease.end_date,
                    "rent_amount": str(active_lease.rent_amount),
                    "active": active_lease.active,
                }

            units_data.append({
                "id": u.id,
                "number": u.number,
                "rent_amount": str(u.rent_amount),
                "status": status,
                "tenant": tenant_info,
                "lease": lease_info,
            })

        return {
            "id": prop.id,
            "name": prop.name,
            "address": prop.address,
            "total_units": len(prop.units),
            "occupied_units": occupied_count,
            "vacant_units": vacant_count,
            "units": units_data
        }

    except HTTPException:
        raise
    except Exception as e:
        print("❌ ERROR inside property_with_units_detailed:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to build property detail")
