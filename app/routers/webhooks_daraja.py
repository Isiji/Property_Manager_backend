# app/routers/webhooks_daraja.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app import models

router = APIRouter(prefix="/payments/webhooks", tags=["Payments: Webhooks"])


def _yyyymm(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


@router.post("/daraja")
async def daraja_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handles LNM Online callback.
    Sandbox payload structure:
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
    """
    body = await request.json()
    stk = body.get("Body", {}).get("stkCallback", {})
    result_code = stk.get("ResultCode", 1)
    meta_items = {i.get("Name"): i.get("Value") for i in stk.get("CallbackMetadata", {}).get("Item", [])} if stk.get("CallbackMetadata") else {}

    # Extract values (some may be missing on failures)
    amount = meta_items.get("Amount")
    receipt = meta_items.get("MpesaReceiptNumber")
    # phone = meta_items.get("PhoneNumber")  # optional, not needed to find the row

    # Strategy: update the latest pending payment for the current month.
    # Alternatively, you can store CheckoutRequestID on initiate and match here.
    period = _yyyymm(date.today())

    p: Optional[models.Payment] = (
        db.query(models.Payment)
        .filter(models.Payment.period == period)
        .order_by(models.Payment.created_at.desc())
        .first()
    )
    if p is None:
        # Nothing to update; ack anyway to avoid retries storm
        return {"ok": True, "skipped": True}

    if result_code == 0:
        p.status = models.PaymentStatus.paid
        p.paid_date = date.today()
        if amount:
            p.amount = amount
        if receipt:
            p.reference = receipt
    else:
        # Keep as pending or mark a failure status if you add one later
        pass

    db.commit()
    return {"ok": True}
