# app/routers/admin_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db, get_current_user, role_required
from app.schemas.admin_schema import AdminCreate, AdminUpdate, AdminOut
from app.crud import admin_crud as crud

router = APIRouter(
    prefix="/admins",
    tags=["Admins"],
)

# -- Policies -------------------------------------------------------------
# - Create admin: only super-admin (role=admin)
# - List admins: only super-admin
# - Get single admin: self OR super-admin
# - Update admin: self OR super-admin
# - Delete admin: super-admin only
# -------------------------------------------------------------------------

@router.post(
    "/",
    response_model=AdminOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(role_required(["admin"]))],
)
def create_admin(payload: AdminCreate, db: Session = Depends(get_db)):
    return crud.create_admin(
        db,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
    )

@router.get(
    "/",
    response_model=List[AdminOut],
    dependencies=[Depends(role_required(["admin"]))],
)
def list_admins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_admins(db, skip, limit)

@router.get("/{admin_id}", response_model=AdminOut)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # allow: super-admin OR the admin themselves
    if current_user.get("role") != "admin" and current_user.get("admin_id") != admin_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this admin")

    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return admin

@router.put("/{admin_id}", response_model=AdminOut)
def update_admin(
    admin_id: int,
    payload: AdminUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # allow: super-admin OR self
    if current_user.get("role") != "admin" and current_user.get("admin_id") != admin_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this admin")

    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    return crud.update_admin(db, admin, payload.dict(exclude_unset=True))

@router.delete(
    "/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(role_required(["admin"]))],
)
def delete_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    crud.delete_admin(db, admin)
    return None
