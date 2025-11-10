from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.schemas.payment_schema import PaymentCreate, PaymentUpdate, PaymentOut
from app.crud import payment_crud
from app import models

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/", response_model=PaymentOut)
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    try:
        return payment_crud.create_payment(db, payment)
    except ValueError as ve:
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


# ---------- NEW: Manual Cash Entry (matches frontend /payments/record) ----------
@router.post("/record", response_model=PaymentOut)
def record_payment(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current: Dict[str, Any] = Depends(get_current_user),
):
    lease_id = payload.get("lease_id")
    period = payload.get("period")
    amount = payload.get("amount")
    paid_date = payload.get("paid_date")

    if not lease_id or not period or amount is None or not paid_date:
        raise HTTPException(status_code=400, detail="lease_id, period, amount, paid_date are required")

    try:
        pd = datetime.fromisoformat(paid_date).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid paid_date")

    lease = db.query(models.Lease).filter(models.Lease.id == int(lease_id)).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()
    unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
    if not tenant or not unit:
        raise HTTPException(status_code=400, detail="Lease links broken")

    # Upsert payment for period
    p = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease.id)
        .filter(models.Payment.period == period)
        .first()
    )
    if p is None:
        p = models.Payment(
            tenant_id=tenant.id,
            unit_id=unit.id,
            lease_id=lease.id,
            amount=amount,
            period=period,
            paid_date=pd,
            reference=None,
            status=models.PaymentStatus.paid,
        )
        db.add(p)
    else:
        p.amount = amount
        p.paid_date = pd
        p.status = models.PaymentStatus.paid

    db.commit()
    db.refresh(p)
    return p


# ---------- NEW: /payments/remind (single) ----------
@router.post("/remind")
def send_reminder_single(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current: Dict[str, Any] = Depends(get_current_user),
):
    lease_id = payload.get("lease_id")
    message = (payload.get("message") or "").strip() or "Kindly clear your rent. Thank you."
    if not lease_id:
        raise HTTPException(status_code=400, detail="lease_id is required")

    lease = db.query(models.Lease).filter(models.Lease.id == int(lease_id)).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    note = models.Notification(
        user_id=tenant.id,
        user_type="tenant",
        title="Rent Reminder",
        message=message,
        channel="in_app",
    )
    db.add(note)
    db.commit()
    return {"ok": True, "notified": tenant.id}


# ---------- NEW: /payments/remind/bulk ----------
@router.post("/remind/bulk")
def send_reminders_bulk(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current: Dict[str, Any] = Depends(get_current_user),
):
    property_id = payload.get("property_id")
    period = payload.get("period")
    message = (payload.get("message") or "").strip() or "Kindly clear your rent for the month. Thank you."
    if not property_id or not period:
        raise HTTPException(status_code=400, detail="property_id and period are required")

    # Unpaid = no payment with status 'paid' for that lease & period
    unpaid: list[int] = []
    # leases on that property (active)
    q = (
        db.query(models.Lease)
        .join(models.Unit, models.Unit.id == models.Lease.unit_id)
        .filter(models.Unit.property_id == int(property_id))
        .filter(models.Lease.active == 1)
    )
    for lease in q.all():
        p = (
            db.query(models.Payment)
            .filter(models.Payment.lease_id == lease.id)
            .filter(models.Payment.period == period)
            .first()
        )
        if not p or p.status != models.PaymentStatus.paid:
            unpaid.append(lease.tenant_id)

    # Create notifications
    sent = 0
    for tid in unpaid:
        note = models.Notification(
            user_id=tid,
            user_type="tenant",
            title=f"Rent Reminder {period}",
            message=message,
            channel="in_app",
        )
        db.add(note)
        sent += 1

    db.commit()
    return {"ok": True, "sent": sent, "period": period}
