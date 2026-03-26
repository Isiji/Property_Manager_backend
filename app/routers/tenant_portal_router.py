# app/routers/tenant_portal_router.py
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
import jwt

from app.database import get_db
from app import models

try:
    from app.core.config import settings
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = getattr(settings, "ALGORITHM", "HS256")
except Exception:
    SECRET_KEY = "CHANGE_ME_SECRET"
    ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/tenants/me", tags=["Tenant Portal"])


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "sub": payload.get("sub"),
            "role": payload.get("role"),
            "exp": payload.get("exp"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_tenant(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> models.Tenant:
    info = _decode_token(token)
    if info.get("role") != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")

    tenant_id = info.get("sub")
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no sub")

    t = (
        db.query(models.Tenant)
        .options(
            joinedload(models.Tenant.leases)
            .joinedload(models.Lease.unit)
            .joinedload(models.Unit.property),
            joinedload(models.Tenant.payments),
            joinedload(models.Tenant.maintenance_requests)
            .joinedload(models.MaintenanceRequest.status),
        )
        .filter(models.Tenant.id == int(tenant_id))
        .first()
    )
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return t


def _yyyymm(dt: date | datetime) -> str:
    return f"{dt.year}-{str(dt.month).zfill(2)}"


def _period_to_date(period: str) -> date:
    y, m = period.split("-")
    return date(int(y), int(m), 1)


def _add_months(period: str, count: int) -> str:
    d = _period_to_date(period)
    month_index = (d.year * 12 + d.month - 1) + count
    y = month_index // 12
    m = (month_index % 12) + 1
    return f"{y}-{str(m).zfill(2)}"


def _sum_allocated_for_period(db: Session, lease_id: int, period: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(models.PaymentAllocation.amount_applied), 0))
        .filter(models.PaymentAllocation.lease_id == lease_id)
        .filter(models.PaymentAllocation.period == period)
        .scalar()
    )
    return float(total or 0)


def _period_status(expected: float, received: float) -> str:
    if expected <= 0:
        return "n/a"
    if received <= 0:
        return "unpaid"
    if received < expected:
        return "partial"
    if received == expected:
        return "paid"
    return "credit"


def _notes_to_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _build_period_suggestions(db: Session, lease: models.Lease) -> Dict[str, Any]:
    rent_amount = float(lease.rent_amount or 0)
    start_period = _yyyymm(lease.start_date.date() if isinstance(lease.start_date, datetime) else lease.start_date)
    current_period = _yyyymm(date.today())

    periods: List[str] = []
    p = start_period
    guard = 0
    while guard < 60:
        periods.append(p)
        if p == _add_months(current_period, 6):
            break
        p = _add_months(p, 1)
        guard += 1

    rows: List[Dict[str, Any]] = []
    unpaid_periods: List[str] = []

    for period in periods:
        received = _sum_allocated_for_period(db, lease.id, period)
        balance = round(rent_amount - received, 2)
        status = _period_status(rent_amount, received)

        row = {
            "period": period,
            "expected": rent_amount,
            "received": received,
            "balance": balance if balance > 0 else 0,
            "status": status,
            "is_past_or_current": period <= current_period,
            "is_future": period > current_period,
        }
        rows.append(row)

        if period <= current_period and received < rent_amount:
            unpaid_periods.append(period)

    if unpaid_periods:
        suggested_periods = unpaid_periods[:3]
        prompt = f"You have arrears for {', '.join(suggested_periods)}. Proceed with payment for these month(s)?"
    else:
        next_period = _add_months(current_period, 1)
        suggested_periods = [next_period]
        prompt = f"You are fully paid up to {current_period}. Proceed to pay {next_period}?"

    return {
        "current_period": current_period,
        "rows": rows,
        "suggested_periods": suggested_periods,
        "prompt": prompt,
    }


def _serialize_rental(db: Session, lease: models.Lease) -> Dict[str, Any]:
    unit = lease.unit
    prop = unit.property if unit else None

    period = _yyyymm(date.today())
    expected = float(lease.rent_amount or 0)
    received = _sum_allocated_for_period(db, lease.id, period)
    balance = round(expected - received, 2)

    return {
        "lease_id": lease.id,
        "active": int(lease.active or 0),
        "start_date": lease.start_date.date().isoformat() if isinstance(lease.start_date, datetime) else (
            lease.start_date.isoformat() if lease.start_date else None
        ),
        "end_date": lease.end_date.date().isoformat() if isinstance(lease.end_date, datetime) and lease.end_date else (
            lease.end_date.isoformat() if lease.end_date else None
        ),
        "rent_amount": float(lease.rent_amount or 0),
        "property": {
            "id": prop.id if prop else None,
            "name": getattr(prop, "name", None),
            "address": getattr(prop, "address", None),
            "property_code": getattr(prop, "property_code", None),
        },
        "unit": {
            "id": unit.id if unit else None,
            "number": getattr(unit, "number", None),
            "property_id": getattr(unit, "property_id", None),
        },
        "this_month": {
            "period": period,
            "expected": expected,
            "received": received,
            "balance": balance if balance > 0 else 0,
            "paid": received >= expected and expected > 0,
            "status": _period_status(expected, received),
        },
        "planner": _build_period_suggestions(db, lease),
    }


@router.get("/overview")
def tenant_overview(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    leases_sorted = sorted(
        current.leases or [],
        key=lambda l: (
            int(l.active or 0),
            l.start_date or datetime.min,
        ),
        reverse=True,
    )

    active_leases = [l for l in leases_sorted if int(l.active or 0) == 1]
    inactive_leases = [l for l in leases_sorted if int(l.active or 0) != 1]

    rentals = [_serialize_rental(db, lease) for lease in active_leases]
    history = [_serialize_rental(db, lease) for lease in inactive_leases[:10]]

    total_expected = sum((r["this_month"]["expected"] or 0) for r in rentals)
    total_received = sum((r["this_month"]["received"] or 0) for r in rentals)
    total_balance = sum((r["this_month"]["balance"] or 0) for r in rentals)

    return {
        "tenant": {
            "id": current.id,
            "name": current.name,
            "phone": current.phone,
            "email": current.email,
            "id_number": getattr(current, "id_number", None),
        },
        "summary": {
            "active_rentals_count": len(rentals),
            "this_month_expected": total_expected,
            "this_month_received": total_received,
            "this_month_balance": total_balance,
        },
        "rentals": rentals,
        "history": history,
    }


@router.get("/profile")
def tenant_profile(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    overview = tenant_overview(current=current, db=db)
    return overview


@router.get("/payments")
def tenant_payments(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    lease_ids = [l.id for l in current.leases]
    if not lease_ids:
        return []

    rows = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.allocations),
            joinedload(models.Payment.unit).joinedload(models.Unit.property),
            joinedload(models.Payment.lease),
        )
        .filter(
            (models.Payment.tenant_id == current.id) |
            (models.Payment.lease_id.in_(lease_ids))
        )
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .all()
    )

    out: List[Dict[str, Any]] = []
    for p in rows:
        allocations = []
        for a in sorted(p.allocations or [], key=lambda x: x.period):
            allocations.append({
                "period": a.period,
                "amount_applied": float(a.amount_applied or 0),
                "lease_id": a.lease_id,
            })

        out.append({
            "id": p.id,
            "tenant_id": p.tenant_id,
            "lease_id": p.lease_id,
            "unit_id": p.unit_id,
            "amount": float(p.amount or 0),
            "reference": p.reference,
            "status": p.status,
            "paid_date": p.paid_date.isoformat() if p.paid_date else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "property_name": getattr(getattr(p.unit, "property", None), "name", None),
            "unit_number": getattr(p.unit, "number", None),
            "allocations": allocations,
        })
    return out


@router.get("/maintenance")
def tenant_maintenance(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = (
        db.query(models.MaintenanceRequest)
        .options(
            joinedload(models.MaintenanceRequest.status),
            joinedload(models.MaintenanceRequest.unit).joinedload(models.Unit.property),
        )
        .filter(models.MaintenanceRequest.tenant_id == current.id)
        .order_by(models.MaintenanceRequest.created_at.desc(), models.MaintenanceRequest.id.desc())
        .all()
    )

    out: List[Dict[str, Any]] = []
    for m in rows:
        out.append({
            "id": m.id,
            "description": m.description,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "status": getattr(getattr(m, "status", None), "name", None),
            "unit_id": getattr(m, "unit_id", None),
            "unit_number": getattr(getattr(m, "unit", None), "number", None),
            "property_name": getattr(getattr(getattr(m, "unit", None), "property", None), "name", None),
        })
    return out