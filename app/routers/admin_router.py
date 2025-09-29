# app/routers/admin_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.admin_schema import AdminCreate, AdminUpdate, AdminOut
from app.crud import admin_crud as crud

router = APIRouter(
    prefix="/admins",
    tags=["Admins"],
)

@router.post("/", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
def create_admin(payload: AdminCreate, db: Session = Depends(get_db)):
    return crud.create_admin(db, name=payload.name, email=payload.email, phone=payload.phone, password=payload.password)

@router.get("/", response_model=List[AdminOut])
def list_admins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_admins(db, skip, limit)

@router.get("/{admin_id}", response_model=AdminOut)
def get_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return admin

@router.put("/{admin_id}", response_model=AdminOut)
def update_admin(admin_id: int, payload: AdminUpdate, db: Session = Depends(get_db)):
    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return crud.update_admin(db, admin, payload.dict(exclude_unset=True))

@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    crud.delete_admin(db, admin)
    return None
