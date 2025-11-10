from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app import models
from app.services.daraja_client import daraja_client

router = APIRouter(prefix="/payments/mpesa", tags=["Payments: M-Pesa"])
webhook_router = APIRouter(prefix="/payments/webhooks", tags=["Payments: Webhooks"])


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

    lease = (
        db.query(models.Lease)
        .filter(models.Lease.id == int(lease_id))
        .filter(models.Lease.active == 1)
        .first()
    )
    if not lease:
        raise HTTPException(status_code=404, detail="Active lease not found")

    if role == "tenant" and lease.tenant_id != sub:
        raise HTTPException(status_code=403, detail="Not your lease")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    msisdn = _to_msisdn254(tenant.phone)
    period = _yyyymm(date.today())

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
            reference=None,
            status=models.PaymentStatus.pending,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    else:
        p.amount = amount
        p.status = models.PaymentStatus.pending
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


@router.post("/simulate/mark-paid")
def simulate_mark_paid(
    payment_id: int,
    reference: str = "SIM-RECEIPT",
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "manager", "landlord"):
        raise HTTPException(status_code=403, detail="Forbidden")

    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    p.status = models.PaymentStatus.paid
    p.paid_date = date.today()
    p.reference = reference
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "ok": True,
        "payment_id": p.id,
        "status": p.status.value,
        "paid_date": p.paid_date.isoformat(),
        "reference": p.reference
    }


@webhook_router.post("/daraja")
async def daraja_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    try:
        stk = payload["Body"]["stkCallback"]
    except Exception:
        return {"ok": True}

    result_code = stk.get("ResultCode")
    items = {it.get("Name"): it.get("Value") for it in stk.get("CallbackMetadata", {}).get("Item", [])}

    phone = str(items.get("PhoneNumber") or "")
    receipt = str(items.get("MpesaReceiptNumber") or "")
    amount = float(items.get("Amount") or 0)

    if result_code == 0 and phone and receipt:
        def _norm(p: str) -> str:
            p = p.strip()
            if p.startswith("+"): p = p[1:]
            if p.startswith("0"): return "254" + p[1:]
            if p.startswith("254"): return p
            if p.startswith("7") and len(p) == 9: return "254" + p
            return p

        msisdn = _norm(phone)
        candidates = [msisdn]
        if msisdn.startswith("254"):
            candidates.append("0" + msisdn[-9:])

        tenant = db.query(models.Tenant).filter(models.Tenant.phone.in_(candidates)).first()
        if tenant:
            p = (
                db.query(models.Payment)
                .filter(models.Payment.tenant_id == tenant.id)
                .filter(models.Payment.status == models.PaymentStatus.pending)
                .order_by(models.Payment.created_at.desc())
                .first()
            )
            if p:
                p.status = models.PaymentStatus.paid
                p.paid_date = date.today()
                p.reference = receipt
                if amount > 0:
                    p.amount = amount
                db.add(p)
                db.commit()

    return {"ok": True}
