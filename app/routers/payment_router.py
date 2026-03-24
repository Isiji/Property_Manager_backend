from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import models
from app.dependencies import get_db, get_current_user
from app.services.daraja_client import daraja_client
from app.services.payment_handler import handle_payment_success

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


def _add_months(period: str, count: int) -> str:
    d = _period_to_date(period)
    month_index = (d.year * 12 + d.month - 1) + count
    y = month_index // 12
    m = (month_index % 12) + 1
    return f"{y}-{str(m).zfill(2)}"


def _normalize_periods(period: Optional[str], periods: Optional[List[str]]) -> List[str]:
    result = []

    if periods:
        for p in periods:
            if not p:
                continue
            _period_to_date(p)
            result.append(p)

    if not result and period:
        _period_to_date(period)
        result.append(period)

    if not result:
        result.append(_yyyymm(date.today()))

    seen = set()
    ordered = []
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


def allocate_payment(
    db: Session,
    *,
    payment: models.Payment,
    lease: models.Lease,
    periods: List[str],
):
    rent = _safe_decimal(lease.rent_amount)
    remaining = _safe_decimal(payment.amount)
    created = []

    for period in periods:
        if remaining <= 0:
            break

        already_paid = _sum_allocated_for_period(db, lease.id, period)
        balance = rent - already_paid

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

    # If payment exceeds selected periods, keep forward credit on last selected period
    if remaining > 0 and periods:
        alloc = models.PaymentAllocation(
            payment_id=payment.id,
            tenant_id=payment.tenant_id,
            unit_id=payment.unit_id,
            lease_id=payment.lease_id,
            period=periods[-1],
            amount_applied=remaining,
        )
        db.add(alloc)
        created.append(alloc)

    return created


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

    lease = _get_lease_or_404(db, int(lease_id))
    periods = _normalize_periods(payload.get("period"), payload.get("periods"))

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
        amount=_safe_decimal(amount),
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

    allocate_payment(
        db,
        payment=payment,
        lease=lease,
        periods=periods,
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

    return {
        "ok": True,
        "payment_id": payment.id,
        "receipt_id": receipt.id if receipt else None,
        "receipt_number": receipt.receipt_number if receipt else None,
        "periods": periods,
    }


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

    lease = _get_lease_or_404(db, int(lease_id))
    tenant = lease.tenant
    unit = lease.unit
    property_ = unit.property if unit else None

    periods = _normalize_periods(payload.get("period"), payload.get("periods"))

    msisdn = phone or getattr(tenant, "phone", None)
    if not msisdn:
        raise HTTPException(status_code=400, detail="Phone number is required")

    account_ref = getattr(property_, "property_code", None) or f"LEASE{lease.id}"
    description = f"Rent payment {periods[0]}"

    stk = daraja_client.initiate_stk_push(
        phone=msisdn.replace("+", ""),
        amount=float(amount),
        account_ref=account_ref,
        description=description,
    )

    payment = models.Payment(
        tenant_id=lease.tenant_id,
        unit_id=lease.unit_id,
        lease_id=lease.id,
        amount=_safe_decimal(amount),
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
        "periods": periods,
    }