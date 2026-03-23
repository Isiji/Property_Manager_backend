from __future__ import annotations

from datetime import date
from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db
from app import models
from app.services.payment_event_service import handle_payment_success

router = APIRouter(prefix="/payments/webhooks", tags=["Payments: Webhooks"])


def _yyyymm(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


def _extract_metadata_items(stk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely convert CallbackMetadata.Item list into a dict.
    Example:
    [
        {"Name": "Amount", "Value": 20000.0},
        {"Name": "MpesaReceiptNumber", "Value": "RKT123ABC"},
        {"Name": "PhoneNumber", "Value": 2547XXXXXXXX}
    ]
    =>
    {
        "Amount": 20000.0,
        "MpesaReceiptNumber": "RKT123ABC",
        "PhoneNumber": 2547XXXXXXXX
    }
    """
    callback_metadata = stk.get("CallbackMetadata") or {}
    items = callback_metadata.get("Item") or []

    result: Dict[str, Any] = {}
    for item in items:
        name = item.get("Name")
        value = item.get("Value")
        if name:
            result[name] = value
    return result


@router.post("/daraja")
async def daraja_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handles M-Pesa LNM Online callback.

    Expected sandbox/live structure:
    {
      "Body": {
        "stkCallback": {
          "MerchantRequestID": "...",
          "CheckoutRequestID": "...",
          "ResultCode": 0,
          "ResultDesc": "The service request is processed successfully.",
          "CallbackMetadata": {
            "Item": [
              {"Name":"Amount","Value":20000.0},
              {"Name":"MpesaReceiptNumber","Value":"RKT1EJ...."},
              {"Name":"Balance"},
              {"Name":"TransactionDate","Value":20251106120134},
              {"Name":"PhoneNumber","Value":2547XXXXXXXX}
            ]
          }
        }
      }
    }

    Current matching strategy:
    - Looks for the latest payment in the current period.
    - Best production upgrade later: save CheckoutRequestID on STK initiate
      and match exactly on callback.
    """

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "detail": "Invalid JSON payload"}

    stk = body.get("Body", {}).get("stkCallback", {})
    result_code = stk.get("ResultCode", 1)
    result_desc = stk.get("ResultDesc", "Unknown callback response")
    merchant_request_id = stk.get("MerchantRequestID")
    checkout_request_id = stk.get("CheckoutRequestID")

    meta_items = _extract_metadata_items(stk)

    amount = meta_items.get("Amount")
    mpesa_receipt = meta_items.get("MpesaReceiptNumber")
    phone_number = meta_items.get("PhoneNumber")
    transaction_date = meta_items.get("TransactionDate")

    # Current month period
    period = _yyyymm(date.today())

    # Load latest payment for this month with all needed relationships eagerly loaded
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
        .filter(models.Payment.period == period)
        .order_by(models.Payment.created_at.desc())
        .first()
    )

    if payment is None:
        # Acknowledge anyway so Daraja doesn't keep retrying forever
        return {
            "ok": True,
            "skipped": True,
            "detail": "No matching payment found",
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
        }

    # If payment is already paid, avoid duplicate receipt generation / duplicate notifications
    if payment.status == models.PaymentStatus.paid:
        return {
            "ok": True,
            "skipped": True,
            "detail": "Payment already processed",
            "payment_id": payment.id,
            "reference": payment.reference,
        }

    if result_code == 0:
        payment.status = models.PaymentStatus.paid
        payment.paid_date = date.today()

        if amount is not None:
            payment.amount = amount

        if mpesa_receipt:
            payment.reference = mpesa_receipt

        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Reload with relationships before event handling
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

        # Trigger receipt generation + notifications
        receipt = handle_payment_success(db, payment)

        return {
            "ok": True,
            "processed": True,
            "payment_id": payment.id,
            "receipt_id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "payment_reference": payment.reference,
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
            "phone_number": phone_number,
            "transaction_date": transaction_date,
            "result_desc": result_desc,
        }

    # Failed callback
    # For now, keep payment pending. Later you can introduce PaymentStatus.failed
    return {
        "ok": True,
        "processed": False,
        "detail": "Payment callback received but transaction not successful",
        "result_code": result_code,
        "result_desc": result_desc,
        "checkout_request_id": checkout_request_id,
        "merchant_request_id": merchant_request_id,
        "phone_number": phone_number,
    }