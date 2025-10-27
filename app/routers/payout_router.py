# app/routers/payout_router.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.payout_schemas import PayoutCreate, PayoutUpdate, PayoutOut
from app.crud import payout_crud

router = APIRouter(prefix="/payouts", tags=["Payouts"])


@router.post("/", response_model=PayoutOut)
def create_payout(payload: PayoutCreate, db: Session = Depends(get_db)):
    try:
        return payout_crud.create_payout(db, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payout_id}", response_model=PayoutOut)
def read_payout(payout_id: int, db: Session = Depends(get_db)):
    p = payout_crud.get_payout(db, payout_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payout not found")
    return p


@router.get("/landlord/{landlord_id}", response_model=List[PayoutOut])
def list_payouts(landlord_id: int, db: Session = Depends(get_db)):
    return payout_crud.list_payouts_for_landlord(db, landlord_id)


@router.put("/{payout_id}", response_model=PayoutOut)
def update_payout(payout_id: int, payload: PayoutUpdate, db: Session = Depends(get_db)):
    p = payout_crud.update_payout(db, payout_id, payload)
    if not p:
        raise HTTPException(status_code=404, detail="Payout not found")
    return p


@router.delete("/{payout_id}", response_model=dict)
def delete_payout(payout_id: int, db: Session = Depends(get_db)):
    ok = payout_crud.delete_payout(db, payout_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Payout not found")
    return {"ok": True}
