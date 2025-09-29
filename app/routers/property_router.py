from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import crud, schemas, models
from app.dependencies import get_db
from app.crud import property_crud

router = APIRouter(prefix="/properties", tags=["Properties"])

# CRUD
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

# Helpers
@router.get("/landlord/{landlord_id}", response_model=List[schemas.PropertyOut])
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    return crud.property_crud.get_properties_by_landlord(db, landlord_id)

@router.get("/manager/{manager_id}", response_model=List[schemas.PropertyOut])
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    return crud.property_crud.get_properties_by_manager(db, manager_id)

@router.get("/{property_id}/with-units-detailed")
def property_with_units_detailed(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property_crud.get_property_with_units(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    units_data = []
    occupied_count = 0
    vacant_count = 0

    for u in prop.units:
        unit_info = {
            "id": u.id,
            "number": u.number,
            "rent_amount": str(u.rent_amount),
            "status": u.status
        }

        if u.status == "occupied" and u.tenant:
            occupied_count += 1
            active_lease = (
                db.query(models.Lease)
                .filter(models.Lease.unit_id == u.id, models.Lease.active == 1)
                .first()
            )
            unit_info["tenant"] = {
                "id": u.tenant.id,
                "name": u.tenant.name,
                "phone": u.tenant.phone,
                "email": u.tenant.email,
            }
            unit_info["lease"] = {
                "id": active_lease.id if active_lease else None,
                "start_date": active_lease.start_date if active_lease else None,
                "end_date": active_lease.end_date if active_lease else None,
            }
        else:
            vacant_count += 1
            unit_info["tenant"] = None
            unit_info["lease"] = None

        units_data.append(unit_info)

    return {
        "id": prop.id,
        "name": prop.name,
        "address": prop.address,
        "total_units": len(prop.units),
        "occupied_units": occupied_count,
        "vacant_units": vacant_count,
        "units": units_data
    }
