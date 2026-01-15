# app/routers/landlord_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db, get_current_user, role_required
from app.schemas.landlord_schema import LandlordCreate, LandlordUpdate, LandlordOut
from app.crud import landlord_crud as crud

router = APIRouter(
    prefix="/landlords",
    tags=["Landlords"],
)

@router.post(
    "/",
    response_model=LandlordOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(role_required(["admin", "property_manager"]))],
)
def create_landlord(payload: LandlordCreate, db: Session = Depends(get_db)):
    return crud.create_landlord(db, name=payload.name, phone=payload.phone, email=payload.email)

@router.get(
    "/",
    response_model=List[LandlordOut],
    dependencies=[Depends(role_required(["admin", "property_manager"]))],
)
def list_landlords(skip: int = 0, limit: int = 100, q: str | None = None, db: Session = Depends(get_db)):
    if q:
        return crud.search_landlords(db, query=q, skip=skip, limit=limit)
    return crud.get_landlords(db, skip, limit)

@router.get("/{landlord_id}", response_model=LandlordOut)
def get_landlord(
    landlord_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role")

    # ✅ allow: admin, property_manager, or landlord self
    if role not in {"admin", "property_manager"}:
        if role == "landlord":
            # 🔥 IMPORTANT FIX:
            # your landlord token contains {sub: "<landlord_id>"} not landlord_id
            try:
                token_sub = int(current_user.get("sub"))
            except Exception:
                token_sub = None

            if token_sub != landlord_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this landlord")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to view this landlord")

    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    return landlord

@router.put("/{landlord_id}", response_model=LandlordOut)
def update_landlord(
    landlord_id: int,
    payload: LandlordUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role")

    is_self = False
    if role == "landlord":
        try:
            token_sub = int(current_user.get("sub"))
        except Exception:
            token_sub = None
        is_self = token_sub == landlord_id

    if not (role == "admin" or is_self):
        raise HTTPException(status_code=403, detail="Not authorized to update this landlord")

    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")

    return crud.update_landlord(db, landlord, payload.dict(exclude_unset=True))

@router.delete(
    "/{landlord_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(role_required(["admin"]))],
)
def delete_landlord(landlord_id: int, db: Session = Depends(get_db)):
    landlord = crud.get_landlord(db, landlord_id)
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    crud.delete_landlord(db, landlord)
    return None
