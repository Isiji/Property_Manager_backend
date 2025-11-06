# app/routers/payments_mpesa.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app import models

router = APIRouter(prefix="/payments/mpesa", tags=["Payments: M-Pesa"])


def _yyyymm(d: date | datetime) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


@router.post("/initiate")
def initiate_stk(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiate M-Pesa STK Push for current month:
    body: { "lease_id": int, "amount": number }
    """
    # Basic payload checks
    lease_id = payload.get("lease_id")
    amount = payload.get("amount")
    if lease_id is None or amount is None:
        raise HTTPException(status_code=400, detail="lease_id and amount are required")

    # Who is paying?
    role = current_user.get("role")
    sub = current_user.get("sub")
    if not role or not sub:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Load lease & ensure it is active
    lease = (
        db.query(models.Lease)
        .filter(models.Lease.id == int(lease_id))
        .filter(models.Lease.active == 1)
        .first()
    )
    if not lease:
        raise HTTPException(status_code=404, detail="Active lease not found")

    # If tenant is initiating: restrict to own lease
    if role == "tenant":
        if lease.tenant_id != int(sub):
            raise HTTPException(status_code=403, detail="Not your lease")
        tenant_id = lease.tenant_id
    else:
        # landlords/managers/admins can initiate on behalf of tenant (future use)
        tenant_id = lease.tenant_id

    # Need tenant & unit for Payment row
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    unit_id = lease.unit_id
    if not unit_id:
        raise HTTPException(status_code=400, detail="Lease has no unit")

    period = _yyyymm(date.today())

    # Create a pending Payment row; reference will be filled on callback
    try:
        p = models.Payment(
            tenant_id=tenant.id,
            unit_id=unit_id,
            lease_id=lease.id,
            amount=amount,
            period=period,
            paid_date=None,
            reference=None,  # will be set with M-Pesa receipt on success
            status=models.PaymentStatus.pending,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        # Unique constraint might fail if you already inserted for this lease+period
        # You can choose to fetch existing pending and reuse:
        existing = (
            db.query(models.Payment)
            .filter(models.Payment.lease_id == lease.id)
            .filter(models.Payment.period == period)
            .first()
        )
        if existing:
            p = existing
        else:
            raise HTTPException(status_code=500, detail=f"Could not create payment: {e}")

    # ───────────────────────────────────────────────────────────────────────────
    # STK INTEGRATION (stub)
    # Here you’d call Safaricom APIs, get CheckoutRequestID/MerchantRequestID,
    # then return a tracking handle to frontend.
    # ───────────────────────────────────────────────────────────────────────────
    # For now, just return a simulated "initiated" response.
    return {
        "ok": True,
        "message": "STK initiated (stub). Complete integration to push to phone.",
        "payment_id": p.id,
        "lease_id": lease.id,
        "tenant_id": tenant.id,
        "unit_id": unit_id,
        "period": period,
        "status": p.status.value,
    }


@router.post("/callback")
def stk_callback(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Safaricom will POST here. Parse result, update Payment.status, reference, paid_date.
    This is a stub you can flesh out when plugging the real API gateway/tunnel.
    """
    # Example expected:
    # payload = {
    #   "ResultCode": 0,
    #   "ResultDesc": "The service request is processed successfully.",
    #   "CheckoutRequestID": "...",
    #   "MpesaReceiptNumber": "AB123XYZ",
    #   "Amount": 20000,
    #   "LeaseId": 6,
    # }
    lease_id = payload.get("LeaseId")
    ref = payload.get("MpesaReceiptNumber")
    amount = payload.get("Amount")
    result_code = payload.get("ResultCode", 1)

    if lease_id is None:
        raise HTTPException(status_code=400, detail="Missing LeaseId")

    period = _yyyymm(date.today())
    p = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == int(lease_id))
        .filter(models.Payment.period == period)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Payment row not found for lease/period")

    if result_code == 0:
        p.status = models.PaymentStatus.paid
        p.paid_date = date.today()
        p.reference = ref
        if amount:
            p.amount = amount
    else:
        # keep pending or add failure handling as you like
        p.status = models.PaymentStatus.pending

    db.commit()
    db.refresh(p)
    return {"ok": True, "payment_id": p.id, "status": p.status.value, "reference": p.reference}
