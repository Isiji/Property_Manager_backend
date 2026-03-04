# app/routers/admin_router.py
from __future__ import annotations

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

# Policies:
# - Create admin: only admin role
# - List admins: only admin role
# - Get single admin: self OR admin role
# - Update admin: self OR admin role
# - Delete admin: only admin role


@router.post(
    "/",
    response_model=AdminOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(role_required(["admin"]))],
)
def create_admin(payload: AdminCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_admin(
            db,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            password=payload.password,
            id_number=getattr(payload, "id_number", None),
        )
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    # current_user is JWT payload: {"sub": "...", "role": "...", ...}
    role = (current_user or {}).get("role")
    sub = (current_user or {}).get("sub")

    # allow: admin role OR the admin themselves
    if role != "admin":
        # if not admin role, must be self
        try:
            if int(sub) != int(admin_id):
                raise HTTPException(status_code=403, detail="Not authorized to view this admin")
        except Exception:
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
    role = (current_user or {}).get("role")
    sub = (current_user or {}).get("sub")

    if role != "admin":
        try:
            if int(sub) != int(admin_id):
                raise HTTPException(status_code=403, detail="Not authorized to update this admin")
        except Exception:
            raise HTTPException(status_code=403, detail="Not authorized to update this admin")

    admin = crud.get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    data = payload.model_dump(exclude_unset=True)
    try:
        return crud.update_admin(db, admin, data)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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