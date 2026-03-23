from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, get_current_user
from app import models
from app.services.daraja_client import daraja_client
from app.services.payment_event_service import handle_payment_success

router = APIRouter(prefix="/payments/mpesa", tags=["Payments: M-Pesa"])
webhook_router = APIRouter(prefix="/payments/webhooks", tags=["Payments: Webhooks"])


def _yyyymm(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


def _to_msisdn254(phone: str) -> str:
    p = phone.strip()
    if p.startswith("+"):
        p = p[1:]
    if p.startswith("0"):
        return "254" + p[1:]
    if p.startswith("254"):
        return p
    if p.startswith("7") and len(p) == 9:
        return "254" + p
    raise HTTPException(
        status_code=400,
        detail="Invalid phone format; expected 07XXXXXXXX or 2547XXXXXXXX"
    )


def _extract_metadata_items(stk: Dict[str, Any]) -> Dict[str, Any]:
    callback_metadata = stk.get("CallbackMetadata") or {}
    items = callback_metadata.get("Item") or []

    result: Dict[str, Any] = {}
    for item in items:
        name = item.get("Name")
        value = item.get("Value")
        if name:
            result[name] = value
    return result


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

    if not tenant.phone:
        raise HTTPException(status_code=400, detail="Tenant phone number is missing")

    msisdn = _to_msisdn254(tenant.phone)
    period = _yyyymm(date.today())

    payment: Optional[models.Payment] = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease.id)
        .filter(models.Payment.period == period)
        .first()
    )

    if payment is None:
        payment = models.Payment(
            tenant_id=tenant.id,
            unit_id=lease.unit_id,
            lease_id=lease.id,
            amount=amount,
            period=period,
            paid_date=None,
            reference=None,
            merchant_request_id=None,
            checkout_request_id=None,
            status=models.PaymentStatus.pending,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
    else:
        # update pending/current payment row for this month
        if payment.status == models.PaymentStatus.paid:
            raise HTTPException(
                status_code=400,
                detail=f"Payment for period {period} is already marked as paid"
            )

        payment.amount = amount
        payment.status = models.PaymentStatus.pending
        payment.reference = None
        payment.paid_date = None
        payment.merchant_request_id = None
        payment.checkout_request_id = None
        db.add(payment)
        db.commit()
        db.refresh(payment)

    account_ref = f"RENT-{payment.id}"
    description = f"Rent {period}"

    daraja_res = daraja_client.initiate_stk_push(
        phone=msisdn,
        amount=amount,
        account_ref=account_ref,
        description=description,
    )

    payment.merchant_request_id = daraja_res.get("MerchantRequestID")
    payment.checkout_request_id = daraja_res.get("CheckoutRequestID")
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "ok": True,
        "message": "STK push sent to phone.",
        "payment_id": payment.id,
        "lease_id": lease.id,
        "tenant_id": tenant.id,
        "period": period,
        "daraja": {
            "MerchantRequestID": payment.merchant_request_id,
            "CheckoutRequestID": payment.checkout_request_id,
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

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease_id)
        .filter(models.Payment.period == period)
        .first()
    )
    if not payment:
        return {"exists": False}

    return {
        "exists": True,
        "status": payment.status.value,
        "paid_date": payment.paid_date.isoformat() if payment.paid_date else None,
        "reference": payment.reference,
        "amount": float(payment.amount),
        "merchant_request_id": payment.merchant_request_id,
        "checkout_request_id": payment.checkout_request_id,
    }


@router.post("/simulate/mark-paid")
def simulate_mark_paid(
    payment_id: int,
    reference: str = "SIM-RECEIPT",
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "manager", "landlord", "super_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.landlord),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.manager),
        )
        .filter(models.Payment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == models.PaymentStatus.paid:
        return {
            "ok": True,
            "message": "Payment already marked as paid",
            "payment_id": payment.id,
            "status": payment.status.value,
            "paid_date": payment.paid_date.isoformat() if payment.paid_date else None,
            "reference": payment.reference,
        }

    payment.status = models.PaymentStatus.paid
    payment.paid_date = date.today()
    payment.reference = reference
    db.add(payment)
    db.commit()
    db.refresh(payment)

    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.landlord),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.manager),
        )
        .filter(models.Payment.id == payment.id)
        .first()
    )

    receipt = handle_payment_success(db, payment)

    return {
        "ok": True,
        "payment_id": payment.id,
        "status": payment.status.value,
        "paid_date": payment.paid_date.isoformat(),
        "reference": payment.reference,
        "receipt_id": receipt.id,
        "receipt_number": receipt.receipt_number,
    }


@webhook_router.post("/daraja")
async def daraja_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "detail": "Invalid JSON payload"}

    stk = payload.get("Body", {}).get("stkCallback", {})
    if not stk:
        return {"ok": True, "skipped": True, "detail": "No stkCallback in payload"}

    result_code = stk.get("ResultCode", 1)
    result_desc = stk.get("ResultDesc", "Unknown callback response")
    merchant_request_id = stk.get("MerchantRequestID")
    checkout_request_id = stk.get("CheckoutRequestID")

    items = _extract_metadata_items(stk)

    amount = items.get("Amount")
    receipt = items.get("MpesaReceiptNumber")
    phone = items.get("PhoneNumber")
    transaction_date = items.get("TransactionDate")

    if not checkout_request_id:
        return {
            "ok": True,
            "skipped": True,
            "detail": "Missing CheckoutRequestID in callback",
            "result_code": result_code,
            "result_desc": result_desc,
        }

    payment: Optional[models.Payment] = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.landlord),
            joinedload(models.Payment.unit)
            .joinedload(models.Unit.property)
            .joinedload(models.Property.manager),
        )
        .filter(models.Payment.checkout_request_id == checkout_request_id)
        .first()
    )

    if payment is None:
        return {
            "ok": True,
            "skipped": True,
            "detail": "No matching payment found for CheckoutRequestID",
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
        }

    if payment.status == models.PaymentStatus.paid:
        return {
            "ok": True,
            "skipped": True,
            "detail": "Payment already processed",
            "payment_id": payment.id,
            "reference": payment.reference,
            "checkout_request_id": checkout_request_id,
        }

    if result_code == 0:
        payment.status = models.PaymentStatus.paid
        payment.paid_date = date.today()

        if amount is not None:
            payment.amount = amount

        if receipt:
            payment.reference = str(receipt)

        if merchant_request_id and not payment.merchant_request_id:
            payment.merchant_request_id = merchant_request_id

        db.add(payment)
        db.commit()
        db.refresh(payment)

        payment = (
            db.query(models.Payment)
            .options(
                joinedload(models.Payment.tenant),
                joinedload(models.Payment.unit)
                .joinedload(models.Unit.property)
                .joinedload(models.Property.landlord),
                joinedload(models.Payment.unit)
                .joinedload(models.Unit.property)
                .joinedload(models.Property.manager),
            )
            .filter(models.Payment.id == payment.id)
            .first()
        )

        receipt_obj = handle_payment_success(db, payment)

        return {
            "ok": True,
            "processed": True,
            "payment_id": payment.id,
            "receipt_id": receipt_obj.id,
            "receipt_number": receipt_obj.receipt_number,
            "payment_reference": payment.reference,
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
            "phone_number": phone,
            "transaction_date": transaction_date,
            "result_desc": result_desc,
        }

    return {
        "ok": True,
        "processed": False,
        "detail": "Payment callback received but transaction not successful",
        "payment_id": payment.id,
        "result_code": result_code,
        "result_desc": result_desc,
        "checkout_request_id": checkout_request_id,
        "merchant_request_id": merchant_request_id,
        "phone_number": phone,
    }