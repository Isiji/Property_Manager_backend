# app/routers/payments_mpesa.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app import models
from app.services.daraja_client import daraja_client

router = APIRouter(prefix="/payments/mpesa", tags=["Payments: M-Pesa"])

def _yyyymm(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"

def _to_msisdn254(phone: str) -> str:
    p = phone.strip()
    if p.startswith("+"): p = p[1:]
    if p.startswith("0"):
        return "254" + p[1:]
    if p.startswith("254"):
        return p
    if p.startswith("7") and len(p) == 9:
        return "254" + p
    raise HTTPException(status_code=400, detail="Invalid phone format; expected 07XXXXXXXX or 2547XXXXXXXX")

@router.post("/initiate")
def initiate_stk(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    lease_id = payload.get("lease_id")
    amount = payload.get("amount")
    if lease_id is None or amount is None:
        raise HTTPException(status_code=400, detail="lease_id and amount are required")

    role = current_user.get("role")
    sub = int(current_user.get("sub", 0) or 0)

    lease = db.query(models.Lease).filter(models.Lease.id == int(lease_id)).filter(models.Lease.active == 1).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Active lease not found")

    if role == "tenant" and lease.tenant_id != sub:
        raise HTTPException(status_code=403, detail="Not your lease")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    msisdn = _to_msisdn254(tenant.phone)
    period = _yyyymm(date.today())

    # ensure/reuse a payment row for this month
    p: Optional[models.Payment] = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease.id)
        .filter(models.Payment.period == period)
        .first()
    )
    if p is None:
        p = models.Payment(
            tenant_id=tenant.id,
            unit_id=lease.unit_id,
            lease_id=lease.id,
            amount=amount,
            period=period,
            paid_date=None,
            reference=None,               # <-- make sure this column exists (see model)
            status=models.PaymentStatus.pending,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    else:
        p.amount = amount
        db.commit()
        db.refresh(p)

    account_ref = f"RENT-{period}".replace("-", "")
    description = f"Rent {period}"

    daraja_res = daraja_client.initiate_stk_push(
        phone=msisdn,
        amount=amount,
        account_ref=account_ref,
        description=description,
    )

    return {
        "ok": True,
        "message": "STK push sent to phone.",
        "payment_id": p.id,
        "lease_id": lease.id,
        "tenant_id": tenant.id,
        "period": period,
        "daraja": {
            "MerchantRequestID": daraja_res.get("MerchantRequestID"),
            "CheckoutRequestID": daraja_res.get("CheckoutRequestID"),
            "ResponseCode": daraja_res.get("ResponseCode"),
            "ResponseDescription": daraja_res.get("ResponseDescription"),
            "CustomerMessage": daraja_res.get("CustomerMessage"),
        },
    }

@router.get("/status")
def payment_status(
    lease_id: int,
    period: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    role = current_user.get("role")
    sub = int(current_user.get("sub", 0) or 0)

    lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    if role == "tenant" and lease.tenant_id != sub:
        raise HTTPException(status_code=403, detail="Not your lease")

    p = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease_id)
        .filter(models.Payment.period == period)
        .first()
    )
    if not p:
        return {"exists": False}

    return {
        "exists": True,
        "status": p.status.value,
        "paid_date": p.paid_date.isoformat() if p.paid_date else None,
        "reference": p.reference,
        "amount": float(p.amount),
    }
