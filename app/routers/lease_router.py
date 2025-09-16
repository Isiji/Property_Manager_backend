from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from .. import crud, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/leases", tags=["Leases"])

@router.post("/", response_model=schemas.LeaseOut)
def create_lease(lease: schemas.LeaseCreate, db: Session = Depends(get_db)):
    return crud.create_lease(db, lease)

@router.get("/", response_model=List[schemas.LeaseOut])
def list_leases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_leases(db, skip, limit)

@router.get("/{lease_id}", response_model=schemas.LeaseOut)
def get_lease(lease_id: int, db: Session = Depends(get_db)):
    return crud.get_lease(db, lease_id)

@router.put("/{lease_id}", response_model=schemas.LeaseOut)
def update_lease(lease_id: int, lease_update: schemas.LeaseUpdate, db: Session = Depends(get_db)):
    return crud.update_lease(db, lease_id, lease_update)

@router.delete("/{lease_id}")
def delete_lease(lease_id: int, db: Session = Depends(get_db)):
    return crud.delete_lease(db, lease_id)
