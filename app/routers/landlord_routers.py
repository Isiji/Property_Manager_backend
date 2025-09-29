# app/routers/landlord_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.landlord_schema import LandlordCreate, LandlordUpdate, LandlordOut
from app.crud import landlord_crud as crud

router = APIRouter(
    prefix="/landlords",
    tags=["Landlords"],
)

@router.post("/", response_model=LandlordOut, status_code=status.HTTP_201_CREATED)
def create_landlord(payload: LandlordCreate, db: Session = Depends(get_db)):
    return crud.create_landlord(db, name=payload.name, phone=payload.phone, email=payload.email)

@router.get("/", response_model=List[LandlordOut])
def list_landlords(skip: int = 0, limit: int = 100, q: str | None = None, db: Session = Depends(get_db)):
    if q:
        return crud.search_landlords(db, query=q, skip=skip, limit=limit)
    return crud.get_landlords(db, skip, limit)

@router.get("/{landlord_id}", response_model=LandlordOut)
def get_landlord(landlord_id: int, db: Session = Depends(get_db)):
    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    return landlord

@router.put("/{landlord_id}", response_model=LandlordOut)
def update_landlord(landlord_id: int, payload: LandlordUpdate, db: Session = Depends(get_db)):
    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    return crud.update_landlord(db, landlord, payload.dict(exclude_unset=True))

@router.delete("/{landlord_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_landlord(landlord_id: int, db: Session = Depends(get_db)):
    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    crud.delete_landlord(db, landlord)
    return None
