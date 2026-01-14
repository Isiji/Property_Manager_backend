# app/routers/unit_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db
from app import schemas
from app.crud import unit_crud
from app.schemas.tenant_schema import TenantOut

router = APIRouter(prefix="/units", tags=["Units"])

@router.post("/", response_model=schemas.UnitOut)
def create_unit(unit: schemas.UnitCreate, db: Session = Depends(get_db)):
    return unit_crud.create_unit(db, unit)

@router.get("/", response_model=List[schemas.UnitOut])
def list_units(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return unit_crud.get_units(db, skip=skip, limit=limit)

# IMPORTANT: put /search BEFORE /{unit_id} to avoid any route confusion
@router.get("/search", response_model=List[schemas.UnitOut])
def search_units(q: str = Query(..., description="Search text for unit number"), db: Session = Depends(get_db)):
    return unit_crud.search_units(db, q)

@router.get("/property/{property_id}", response_model=List[schemas.UnitOut])
def list_units_by_property(property_id: int, db: Session = Depends(get_db)):
    units = unit_crud.get_units_by_property(db, property_id)
    if not units:
        raise HTTPException(status_code=404, detail="No units found for this property")
    return units

@router.get("/available", response_model=List[schemas.UnitOut])
def list_available_units(db: Session = Depends(get_db)):
    return unit_crud.get_available_units(db)

@router.get("/occupied", response_model=List[schemas.UnitOut])
def list_occupied_units(db: Session = Depends(get_db)):
    return unit_crud.get_occupied_units(db)

@router.get("/{unit_id}", response_model=schemas.UnitOut)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = unit_crud.get_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit

@router.get("/{unit_id}/tenant", response_model=TenantOut)
def get_unit_tenant(unit_id: int, db: Session = Depends(get_db)):
    tenant = unit_crud.get_unit_tenant(db, unit_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="No active tenant in this unit")
    return tenant

@router.put("/{unit_id}", response_model=schemas.UnitOut)
def update_unit(unit_id: int, unit_update: schemas.UnitUpdate, db: Session = Depends(get_db)):
    unit = unit_crud.update_unit(db, unit_id, unit_update)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit

@router.delete("/{unit_id}")
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = unit_crud.delete_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"message": "Unit deleted successfully"}
