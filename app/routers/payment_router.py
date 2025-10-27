# app/routers/payment_router.py
from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.payment_schema import PaymentCreate, PaymentUpdate, PaymentOut
from app.crud import payment_crud

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/", response_model=PaymentOut)
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    try:
        return payment_crud.create_payment(db, payment)
    except ValueError as ve:
        # Duplicate period for the same lease, etc.
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{payment_id}", response_model=PaymentOut)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    p = payment_crud.get_payment(db, payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@router.get("/", response_model=List[PaymentOut])
def list_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return payment_crud.get_payments(db, skip=skip, limit=limit)


@router.put("/{payment_id}", response_model=PaymentOut)
def update_payment(payment_id: int, update_data: PaymentUpdate, db: Session = Depends(get_db)):
    p = payment_crud.update_payment(db, payment_id, update_data)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@router.delete("/{payment_id}", response_model=dict)
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    ok = payment_crud.delete_payment(db, payment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"ok": True, "message": "Payment deleted"}


@router.get("/by-tenant/{tenant_id}", response_model=List[PaymentOut])
def payments_by_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_tenant(db, tenant_id)


@router.get("/by-unit/{unit_id}", response_model=List[PaymentOut])
def payments_by_unit(unit_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_unit(db, unit_id)


@router.get("/by-lease/{lease_id}", response_model=List[PaymentOut])
def payments_by_lease(lease_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_lease(db, lease_id)


@router.get("/by-date-range/", response_model=List[PaymentOut])
def payments_by_date_range(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
):
    return payment_crud.get_payments_by_date_range(db, start_date, end_date)
