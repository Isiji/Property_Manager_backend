from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import crud, schemas
from app.dependencies import get_db

router = APIRouter(prefix="/properties", tags=["Properties"])

# CRUD
@router.post("/", response_model=schemas.PropertyOut)
def create_property(payload: schemas.PropertyCreate, db: Session = Depends(get_db)):
    return crud.property.create_property(db, payload)

@router.get("/", response_model=List[schemas.PropertyOut])
def list_properties(db: Session = Depends(get_db)):
    return crud.property.get_properties(db)

@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(property_id: int, payload: schemas.PropertyUpdate, db: Session = Depends(get_db)):
    prop = crud.property.update_property(db, property_id, payload)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@router.delete("/{property_id}", response_model=schemas.PropertyOut)
def delete_property(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property.delete_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

# Helpers
@router.get("/landlord/{landlord_id}", response_model=List[schemas.PropertyOut])
def properties_by_landlord(landlord_id: int, db: Session = Depends(get_db)):
    return crud.property.get_properties_by_landlord(db, landlord_id)

@router.get("/manager/{manager_id}", response_model=List[schemas.PropertyOut])
def properties_by_manager(manager_id: int, db: Session = Depends(get_db)):
    return crud.property.get_properties_by_manager(db, manager_id)

@router.get("/{property_id}/with-units")
def property_with_units(property_id: int, db: Session = Depends(get_db)):
    prop = crud.property.get_property_with_units(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "id": prop.id,
        "name": prop.name,
        "address": prop.address,
        "units": [{"id": u.id, "number": u.number, "rent_amount": str(u.rent_amount)} for u in prop.units]
    }
