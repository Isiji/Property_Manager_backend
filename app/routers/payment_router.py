from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from .. import schemas
from ..dependencies import get_db
from app.crud import payment_crud

router = APIRouter(prefix="/payments", tags=["Payments"])

# Create Payment
@router.post("/", response_model=schemas.PaymentOut)
def create_payment(payment: schemas.PaymentCreate, db: Session = Depends(get_db)):
    return payment_crud.create_payment(db, payment)

# Get Payment by ID
@router.get("/{payment_id}", response_model=schemas.PaymentOut)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    db_payment = payment_crud.get_payment(db, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return db_payment

# List Payments
@router.get("/", response_model=List[schemas.PaymentOut])
def list_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return payment_crud.get_payments(db, skip=skip, limit=limit)

# Update Payment
@router.put("/{payment_id}", response_model=schemas.PaymentOut)
def update_payment(payment_id: int, update_data: schemas.PaymentUpdate, db: Session = Depends(get_db)):
    db_payment = payment_crud.update_payment(db, payment_id, update_data)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return db_payment

# Delete Payment
@router.delete("/{payment_id}", response_model=dict)
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    success = payment_crud.delete_payment(db, payment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"ok": True, "message": "Payment deleted"}


# Filter by tenant
@router.get("/by-tenant/{tenant_id}", response_model=List[schemas.PaymentOut])
def payments_by_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_tenant(db, tenant_id)

# Filter by unit
@router.get("/by-unit/{unit_id}", response_model=List[schemas.PaymentOut])
def payments_by_unit(unit_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_unit(db, unit_id)

# Filter by lease
@router.get("/by-lease/{lease_id}", response_model=List[schemas.PaymentOut])
def payments_by_lease(lease_id: int, db: Session = Depends(get_db)):
    return payment_crud.get_payments_by_lease(db, lease_id)

# Filter by date range
@router.get("/by-date-range/", response_model=List[schemas.PaymentOut])
def payments_by_date_range(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db)
):
    return payment_crud.get_payments_by_date_range(db, start_date, end_date)
