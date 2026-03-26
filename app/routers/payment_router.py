from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models
from app.dependencies import get_db, get_current_user
from app.services.daraja_service import daraja_client
from app.services.payment_event_service import handle_payment_success

router = APIRouter(prefix="/payments", tags=["Payments"])


def _safe_decimal(v) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except Exception:
        return Decimal("0")


def _yyyymm(d: date) -> str:
    return f"{d.year}-{str(d.month).zfill(2)}"


def _period_to_date(period: str) -> date:
    try:
        y, m = period.split("-")
        return date(int(y), int(m), 1)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid period format. Use YYYY-MM")


def _normalize_periods(period: Optional[str], periods: Optional[List[str]]) -> List[str]:
    result: List[str] = []

    if periods:
      for p in periods:
            if not p:
                continue
            p = str(p).strip()
            _period_to_date(p)
            result.append(p)

    if not result and period:
        p = str(period).strip()
        _period_to_date(p)
        result.append(p)

    if not result:
        result.append(_yyyymm(date.today()))

    seen = set()
    ordered: List[str] = []
    for p in result:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    ordered.sort()
    return ordered


def _get_lease_or_404(db: Session, lease_id: int) -> models.Lease:
    lease = (
        db.query(models.Lease)
        .options(
            joinedload(models.Lease.tenant),
            joinedload(models.Lease.unit).joinedload(models.Unit.property),
            joinedload(models.Lease.payments).joinedload(models.Payment.allocations),
        )
        .filter(models.Lease.id == lease_id)
        .first()
    )
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


def _sum_allocated_for_period(db: Session, lease_id: int, period: str) -> Decimal:
    allocations = (
        db.query(models.PaymentAllocation)
        .filter(models.PaymentAllocation.lease_id == lease_id)
        .filter(models.PaymentAllocation.period == period)
        .all()
    )
    total = Decimal("0")
    for a in allocations:
        total += _safe_decimal(a.amount_applied)
    return total


def _period_balance(db: Session, lease: models.Lease, period: str) -> Decimal:
    rent = _safe_decimal(lease.rent_amount)
    already_paid = _sum_allocated_for_period(db, lease.id, period)
    balance = rent - already_paid
    if balance < Decimal("0"):
        return Decimal("0")
    return balance


def _validate_periods_not_fully_paid(db: Session, lease: models.Lease, periods: List[str]) -> None:
    fully_paid: List[str] = []
    for period in periods:
        if _period_balance(db, lease, period) <= Decimal("0"):
            fully_paid.append(period)

    if fully_paid:
        joined = ", ".join(fully_paid)
        raise HTTPException(
            status_code=400,
            detail=f"The following month(s) are already fully paid: {joined}. Choose another month."
        )


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


def _extract_callback_metadata_items(stk: Dict[str, Any]) -> Dict[str, Any]:
    callback_metadata = stk.get("CallbackMetadata") or {}
    items = callback_metadata.get("Item") or []

    result: Dict[str, Any] = {}
    for item in items:
        name = item.get("Name")
        value = item.get("Value")
        if name:
            result[name] = value
    return result


def _format_mpesa_transaction_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        dt_obj = datetime.strptime(s, "%Y%m%d%H%M%S")
        return dt_obj.isoformat()
    except Exception:
        return s


def _build_mpesa_notes(
    *,
    existing_notes: Optional[str],
    result_code: Any,
    result_desc: Any,
    merchant_request_id: Any,
    checkout_request_id: Any,
    amount: Any = None,
    receipt: Any = None,
    phone: Any = None,
    transaction_date: Any = None,
    unapplied_amount: Any = None,
) -> str:
    data: Dict[str, Any] = {}

    if existing_notes:
        try:
            maybe = json.loads(existing_notes)
            if isinstance(maybe, dict):
                data = maybe
        except Exception:
            data = {}

    data.update({
        "provider": "mpesa",
        "result_code": result_code,
        "result_desc": result_desc,
        "merchant_request_id": merchant_request_id,
        "checkout_request_id": checkout_request_id,
        "mpesa_amount": float(amount) if amount is not None else None,
        "mpesa_receipt_number": str(receipt) if receipt is not None else None,
        "mpesa_phone_number": str(phone) if phone is not None else None,
        "mpesa_transaction_date_raw": str(transaction_date) if transaction_date is not None else None,
        "mpesa_transaction_date_iso": _format_mpesa_transaction_date(transaction_date),
        "unapplied_amount": float(unapplied_amount) if unapplied_amount is not None else None,
    })

    return json.dumps(data)


def allocate_payment(
    db: Session,
    *,
    payment: models.Payment,
    lease: models.Lease,
    periods: List[str],
) -> Dict[str, Any]:
    existing_allocs = (
        db.query(models.PaymentAllocation)
        .filter(models.PaymentAllocation.payment_id == payment.id)
        .all()
    )
    if existing_allocs:
        total_existing = sum((_safe_decimal(a.amount_applied) for a in existing_allocs), Decimal("0"))
        return {
            "allocations": existing_allocs,
            "remaining": _safe_decimal(payment.amount) - total_existing,
        }

    remaining = _safe_decimal(payment.amount)
    created = []

    for period in periods:
        if remaining <= 0:
            break

        balance = _period_balance(db, lease, period)
        if balance <= 0:
            continue

        apply_amt = balance if remaining >= balance else remaining

        alloc = models.PaymentAllocation(
            payment_id=payment.id,
            tenant_id=payment.tenant_id,
            unit_id=payment.unit_id,
            lease_id=payment.lease_id,
            period=period,
            amount_applied=apply_amt,
        )
        db.add(alloc)
        created.append(alloc)
        remaining -= apply_amt

    # keep excess as explicit credit row instead of silently overpaying a cleared month
    if remaining > 0:
        credit_alloc = models.PaymentAllocation(
            payment_id=payment.id,
            tenant_id=payment.tenant_id,
            unit_id=payment.unit_id,
            lease_id=payment.lease_id,
            period="CREDIT",
            amount_applied=remaining,
        )
        db.add(credit_alloc)
        created.append(credit_alloc)

    return {
        "allocations": created,
        "remaining": remaining,
    }


def _serialize_payment_response(payment: models.Payment, periods: List[str], receipt_obj=None) -> Dict[str, Any]:
    return {
        "ok": True,
        "payment_id": payment.id,
        "receipt_id": receipt_obj.id if receipt_obj else None,
        "receipt_number": receipt_obj.receipt_number if receipt_obj else None,
        "periods": periods,
        "amount": float(payment.amount or 0),
    }


@router.post("/record")
def record_payment(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    lease_id = payload.get("lease_id")
    amount = payload.get("amount")

    if not lease_id:
        raise HTTPException(status_code=400, detail="lease_id is required")
    if amount is None:
        raise HTTPException(status_code=400, detail="amount is required")

    amount_dec = _safe_decimal(amount)
    if amount_dec <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    lease = _get_lease_or_404(db, int(lease_id))
    periods = _normalize_periods(payload.get("period"), payload.get("periods"))
    _validate_periods_not_fully_paid(db, lease, periods)

    paid_date_raw = payload.get("paid_date")
    if paid_date_raw:
        try:
            paid_date_value = datetime.fromisoformat(str(paid_date_raw)).date()
        except Exception:
            try:
                paid_date_value = date.fromisoformat(str(paid_date_raw))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid paid_date format")
    else:
        paid_date_value = date.today()

    payment = models.Payment(
        tenant_id=lease.tenant_id,
        unit_id=lease.unit_id,
        lease_id=lease.id,
        amount=amount_dec,
        period=periods[0],
        paid_date=paid_date_value,
        reference=payload.get("reference"),
        payment_method=payload.get("method", "cash"),
        allocation_mode="manual",
        selected_periods_json=json.dumps(periods),
        notes=payload.get("notes"),
        status=models.PaymentStatus.paid,
    )

    db.add(payment)
    db.flush()

    alloc_result = allocate_payment(
        db,
        payment=payment,
        lease=lease,
        periods=periods,
    )

    payment.notes = _build_mpesa_notes(
        existing_notes=payment.notes,
        result_code=0,
        result_desc="Manual payment recorded",
        merchant_request_id=None,
        checkout_request_id=None,
        amount=payment.amount,
        receipt=payment.reference,
        phone=None,
        transaction_date=None,
        unapplied_amount=alloc_result["remaining"],
    )

    db.commit()

    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.allocations),
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit).joinedload(models.Unit.property),
        )
        .filter(models.Payment.id == payment.id)
        .first()
    )

    receipt = handle_payment_success(db, payment)
    return _serialize_payment_response(payment, periods, receipt)


@router.post("/mpesa/initiate")
def initiate_mpesa(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    lease_id = payload.get("lease_id")
    amount = payload.get("amount")
    phone = payload.get("phone")

    if not lease_id:
        raise HTTPException(status_code=400, detail="lease_id is required")
    if amount is None:
        raise HTTPException(status_code=400, detail="amount is required")

    amount_dec = _safe_decimal(amount)
    if amount_dec <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    lease = _get_lease_or_404(db, int(lease_id))
    tenant = lease.tenant
    unit = lease.unit
    property_ = unit.property if unit else None

    periods = _normalize_periods(payload.get("period"), payload.get("periods"))
    _validate_periods_not_fully_paid(db, lease, periods)

    msisdn_raw = phone or getattr(tenant, "phone", None)
    if not msisdn_raw:
        raise HTTPException(status_code=400, detail="Phone number is required")

    msisdn = _to_msisdn254(msisdn_raw)

    role = current.get("role")
    sub = int(current.get("sub", 0) or 0)
    if role == "tenant" and lease.tenant_id != sub:
        raise HTTPException(status_code=403, detail="Not your lease")

    account_ref = getattr(property_, "property_code", None) or f"LEASE{lease.id}"
    description = f"Rent payment {periods[0]}"

    try:
        stk = daraja_client.initiate_stk_push(
            phone=msisdn,
            amount=float(amount_dec),
            account_ref=account_ref,
            description=description,
        )
    except Exception:
        db.rollback()
        raise

    payment = models.Payment(
        tenant_id=lease.tenant_id,
        unit_id=lease.unit_id,
        lease_id=lease.id,
        amount=amount_dec,
        period=periods[0],
        paid_date=None,
        reference=None,
        merchant_request_id=stk.get("MerchantRequestID"),
        checkout_request_id=stk.get("CheckoutRequestID"),
        payment_method="M-Pesa",
        allocation_mode="planned",
        selected_periods_json=json.dumps(periods),
        notes=payload.get("notes"),
        status=models.PaymentStatus.pending,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "ok": True,
        "message": stk.get("CustomerMessage") or "STK push initiated",
        "payment_id": payment.id,
        "checkout_request_id": payment.checkout_request_id,
        "merchant_request_id": payment.merchant_request_id,
        "periods": periods,
        "amount": float(payment.amount),
    }


@router.post("/webhooks/daraja")
async def daraja_callback(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    stk = data.get("Body", {}).get("stkCallback", {})
    if not stk:
        return {
            "ResultCode": 0,
            "ResultDesc": "No stkCallback in payload",
        }

    result_code = stk.get("ResultCode", 1)
    result_desc = stk.get("ResultDesc", "Unknown callback response")
    merchant_request_id = stk.get("MerchantRequestID")
    checkout_request_id = stk.get("CheckoutRequestID")

    items = _extract_callback_metadata_items(stk)
    amount = items.get("Amount")
    receipt = items.get("MpesaReceiptNumber")
    phone = items.get("PhoneNumber")
    transaction_date = items.get("TransactionDate")

    if not checkout_request_id:
        return {
            "ResultCode": 0,
            "ResultDesc": "Missing CheckoutRequestID in callback",
        }

    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.allocations),
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit).joinedload(models.Unit.property),
        )
        .filter(models.Payment.checkout_request_id == checkout_request_id)
        .first()
    )

    if payment is None and merchant_request_id:
        payment = (
            db.query(models.Payment)
            .options(
                joinedload(models.Payment.allocations),
                joinedload(models.Payment.tenant),
                joinedload(models.Payment.unit).joinedload(models.Unit.property),
            )
            .filter(models.Payment.merchant_request_id == merchant_request_id)
            .order_by(models.Payment.created_at.desc())
            .first()
        )

    if payment is None:
        return {
            "ResultCode": 0,
            "ResultDesc": "No matching payment found",
        }

    if payment.status == models.PaymentStatus.paid:
        return {
            "ResultCode": 0,
            "ResultDesc": "Payment already processed",
        }

    if result_code != 0:
        payment.status = models.PaymentStatus.failed
        payment.notes = _build_mpesa_notes(
            existing_notes=payment.notes,
            result_code=result_code,
            result_desc=result_desc,
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            amount=amount,
            receipt=receipt,
            phone=phone,
            transaction_date=transaction_date,
            unapplied_amount=None,
        )
        db.add(payment)
        db.commit()

        return {
            "ResultCode": 0,
            "ResultDesc": "Failure callback processed",
        }

    if amount is not None:
        payment.amount = _safe_decimal(amount)

    if receipt:
        payment.reference = str(receipt)

    if merchant_request_id and not payment.merchant_request_id:
        payment.merchant_request_id = merchant_request_id

    payment.status = models.PaymentStatus.paid
    payment.paid_date = date.today()

    periods: List[str] = []
    if payment.selected_periods_json:
        try:
            maybe = json.loads(payment.selected_periods_json)
            if isinstance(maybe, list):
                periods = [str(x) for x in maybe if str(x).strip()]
        except Exception:
            periods = []

    if not periods and payment.period:
        periods = [payment.period]

    lease = _get_lease_or_404(db, payment.lease_id)

    alloc_result = allocate_payment(
        db,
        payment=payment,
        lease=lease,
        periods=periods,
    )

    payment.notes = _build_mpesa_notes(
        existing_notes=payment.notes,
        result_code=result_code,
        result_desc=result_desc,
        merchant_request_id=merchant_request_id,
        checkout_request_id=checkout_request_id,
        amount=amount,
        receipt=receipt,
        phone=phone,
        transaction_date=transaction_date,
        unapplied_amount=alloc_result["remaining"],
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.allocations),
            joinedload(models.Payment.tenant),
            joinedload(models.Payment.unit).joinedload(models.Unit.property),
        )
        .filter(models.Payment.id == payment.id)
        .first()
    )

    try:
        receipt_obj = handle_payment_success(db, payment)
    except Exception:
        receipt_obj = None

    return {
        "ResultCode": 0,
        "ResultDesc": "Success callback processed",
        "ok": True,
        "processed": True,
        "payment_id": payment.id,
        "receipt_id": receipt_obj.id if receipt_obj else None,
        "receipt_number": receipt_obj.receipt_number if receipt_obj else None,
        "payment_reference": payment.reference,
        "checkout_request_id": checkout_request_id,
        "merchant_request_id": merchant_request_id,
        "phone_number": phone,
        "transaction_date": transaction_date,
        "amount": float(payment.amount or 0),
    }