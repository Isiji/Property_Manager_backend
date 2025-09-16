# app/routers/landlords.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List

from app import models
from app.dependencies import get_db
from app.schemas.landlord_schema import LandlordCreate, LandlordUpdate, LandlordOut

router = APIRouter(
    prefix="/landlords",
    tags=["Landlords"],
)

@router.post("/", response_model=LandlordOut, status_code=status.HTTP_201_CREATED)
def create_landlord(payload: LandlordCreate, db: Session = Depends(get_db)):
    filters = []
    if payload.email:
        filters.append(models.Landlord.email == payload.email)
    if payload.phone:
        filters.append(models.Landlord.phone == payload.phone)

    exists = db.query(models.Landlord).filter(or_(*filters)).first() if filters else None
    if exists:
        raise HTTPException(status_code=400, detail="Landlord with email or phone already exists")

    obj = models.Landlord(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/", response_model=List[LandlordOut])
def list_landlords(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Landlord).offset(skip).limit(limit).all()

@router.get("/{landlord_id}", response_model=LandlordOut)
def get_landlord(landlord_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Landlord).filter(models.Landlord.id == landlord_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Landlord not found")
    return obj

@router.put("/{landlord_id}", response_model=LandlordOut)
def update_landlord(landlord_id: int, payload: LandlordUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.Landlord).filter(models.Landlord.id == landlord_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Landlord not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(obj, key, value)

    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{landlord_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_landlord(landlord_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Landlord).filter(models.Landlord.id == landlord_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Landlord not found")

    db.delete(obj)
    db.commit()
    return None
