from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db
from app.schemas.property_manager_schema import (
    PropertyManagerCreate, PropertyManagerUpdate, PropertyManagerOut
)
from app.crud import property_manager_crud as crud

router = APIRouter(
    prefix="/managers",
    tags=["Property Managers"],
)

@router.post("/", response_model=PropertyManagerOut, status_code=status.HTTP_201_CREATED)
def create_property_manager(payload: PropertyManagerCreate, db: Session = Depends(get_db)):
    return crud.create_property_manager(db, name=payload.name, phone=payload.phone, email=payload.email)

@router.get("/", response_model=List[PropertyManagerOut])
def list_property_managers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_property_managers(db, skip, limit)

@router.get("/{manager_id}", response_model=PropertyManagerOut)
def get_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = crud.get_property_manager(db, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")
    return manager

@router.put("/{manager_id}", response_model=PropertyManagerOut)
def update_property_manager(manager_id: int, payload: PropertyManagerUpdate, db: Session = Depends(get_db)):
    manager = crud.get_property_manager(db, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")
    return crud.update_property_manager(db, manager, payload.dict(exclude_unset=True))

@router.delete("/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = crud.get_property_manager(db, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Property Manager not found")
    crud.delete_property_manager(db, manager)
    return None
