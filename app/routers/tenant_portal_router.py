# tenant_portal_router.py
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

from app.services import notification_service
from app.schemas.notification_schema import NotificationCreate

try:
    from app.core.config import settings
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = getattr(settings, "ALGORITHM", "HS256")
except Exception:
    SECRET_KEY = "CHANGE_ME_SECRET"
    ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
            joinedload(models.Tenant.leases).joinedload(models.Lease.unit).joinedload(models.Unit.property),
            joinedload(models.Tenant.payments),
            joinedload(models.Tenant.maintenance_requests).joinedload(models.MaintenanceRequest.status),
        )
        .filter(models.Tenant.id == int(tenant_id))
        .first()
    )
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return t


router = APIRouter(prefix="/tenants/me", tags=["Tenant Portal"])


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


def _list_periods(start_period: str, months: int) -> List[str]:
    return [_add_months(start_period, i) for i in range(months)]


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


@router.get("/overview")
def tenant_overview(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    active_lease: Optional[models.Lease] = None
    for l in current.leases:
        if int(l.active or 0) == 1:
            active_lease = l
            break

    unit_info: Dict[str, Any] = {}
    lease_info: Dict[str, Any] = {}
    this_month: Dict[str, Any] = {"expected": 0, "received": 0, "balance": 0, "paid": False}
    planner: Dict[str, Any] = {"rows": [], "suggested_periods": [], "prompt": ""}

    if active_lease:
        unit = active_lease.unit
        unit_info = {
            "id": unit.id if unit else None,
            "number": getattr(unit, "number", None),
            "property_id": getattr(unit, "property_id", None),
            "property_name": getattr(unit.property, "name", None) if unit and unit.property else None,
        }
        lease_info = {
            "id": active_lease.id,
            "rent_amount": float(active_lease.rent_amount) if active_lease.rent_amount is not None else None,
            "start_date": active_lease.start_date.date().isoformat() if isinstance(active_lease.start_date, datetime) else active_lease.start_date.isoformat(),
            "end_date": active_lease.end_date.date().isoformat() if isinstance(active_lease.end_date, datetime) and active_lease.end_date else (active_lease.end_date.isoformat() if active_lease.end_date else None),
            "active": int(active_lease.active),
        }

        period = _yyyymm(date.today())
        expected = float(active_lease.rent_amount or 0)
        received = _sum_allocated_for_period(db, active_lease.id, period)
        balance = round(expected - received, 2)

        this_month = {
            "period": period,
            "expected": expected,
            "received": received,
            "balance": balance if balance > 0 else 0,
            "paid": received >= expected and expected > 0,
            "status": _period_status(expected, received),
        }

        planner = _build_period_suggestions(db, active_lease)

    return {
        "tenant": {
            "id": current.id,
            "name": current.name,
            "phone": current.phone,
            "email": current.email,
            "id_number": getattr(current, "id_number", None),
        },
        "unit": unit_info,
        "lease": lease_info,
        "this_month": this_month,
        "planner": planner,
    }


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
        .filter(models.Payment.tenant_id == current.id)
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .all()
    )

    if not rows:
        rows = (
            db.query(models.Payment)
            .options(
                joinedload(models.Payment.allocations),
                joinedload(models.Payment.unit).joinedload(models.Unit.property),
                joinedload(models.Payment.lease),
            )
            .filter(models.Payment.lease_id.in_(lease_ids))
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
            })

        out.append({
            "id": p.id,
            "lease_id": p.lease_id,
            "tenant_id": p.tenant_id,
            "unit_id": p.unit_id,
            "period": p.period,
            "amount": float(p.amount or 0),
            "paid_date": p.paid_date.isoformat() if p.paid_date else None,
            "reference": getattr(p, "reference", None),
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "payment_method": getattr(p, "payment_method", None),
            "allocation_mode": getattr(p, "allocation_mode", None),
            "selected_periods_json": getattr(p, "selected_periods_json", None),
            "merchant_request_id": getattr(p, "merchant_request_id", None),
            "checkout_request_id": getattr(p, "checkout_request_id", None),
            "notes": _notes_to_dict(getattr(p, "notes", None)),
            "created_at": p.created_at.isoformat() if p.created_at else None,
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
        .filter(models.MaintenanceRequest.tenant_id == current.id)
        .order_by(models.MaintenanceRequest.created_at.desc().nullslast())
        .all()
    )
    out = []
    for m in rows:
        out.append({
            "id": m.id,
            "description": m.description,
            "status": getattr(m.status, "name", None),
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        })
    return out


@router.post("/maintenance", status_code=201)
def create_maintenance(
    payload: Dict[str, Any],
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    description = (payload.get("description") or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description is required")

    status_row = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.name == "open").first()
    if not status_row:
        status_row = models.MaintenanceStatus(name="open")
        db.add(status_row)
        db.commit()
        db.refresh(status_row)

    unit_id = current.unit_id
    if not unit_id:
        active = next((l for l in current.leases if int(l.active or 0) == 1), None)
        if active:
            unit_id = active.unit_id
    if not unit_id:
        raise HTTPException(status_code=400, detail="No unit found for tenant")

    req = models.MaintenanceRequest(
        tenant_id=current.id,
        unit_id=unit_id,
        description=description,
        status_id=status_row.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    unit_row = (
        db.query(models.Unit)
        .options(joinedload(models.Unit.property))
        .filter(models.Unit.id == unit_id)
        .first()
    )

    unit_label = getattr(unit_row, "number", None) or f"Unit {unit_id}"
    title = "New maintenance request"
    message = f"{unit_label}: {description}"

    property_row = getattr(unit_row, "property", None)

    if property_row and getattr(property_row, "landlord_id", None):
        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=property_row.landlord_id,
                user_type="landlord",
                title=title,
                message=message,
                channel="inapp",
            ),
        )

    if property_row and getattr(property_row, "manager_id", None):
        notification_service.send_notification(
            db,
            NotificationCreate(
                user_id=property_row.manager_id,
                user_type="property_manager",
                title=title,
                message=message,
                channel="inapp",
            ),
        )

    return {
        "id": req.id,
        "description": req.description,
        "status": getattr(req.status, "name", None),
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.get("/profile")
def tenant_profile(current: models.Tenant = Depends(get_current_tenant)) -> Dict[str, Any]:
    return {
        "id": current.id,
        "name": current.name,
        "phone": current.phone,
        "email": current.email,
        "property_id": current.property_id,
        "unit_id": current.unit_id,
        "id_number": getattr(current, "id_number", None),
    }


@router.post("/pay")
def pay_this_month(current: models.Tenant = Depends(get_current_tenant)) -> Dict[str, Any]:
    return {"message": "Payment initiation stubbed. Integrate with your PSP here."}


def _get_active_lease_for_tenant(db: Session, tenant_id: int) -> Optional[models.Lease]:
    return (
        db.query(models.Lease)
        .options(
            joinedload(models.Lease.unit).joinedload(models.Unit.property),
        )
        .filter(models.Lease.tenant_id == tenant_id)
        .filter(models.Lease.active == 1)
        .order_by(models.Lease.id.desc())
        .first()
    )


@router.get("/overview")
def tenant_overview(
    current: models.Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    active_lease: Optional[models.Lease] = _get_active_lease_for_tenant(db, current.id)

    unit_info: Dict[str, Any] = {}
    lease_info: Dict[str, Any] = {}
    this_month: Dict[str, Any] = {"expected": 0, "received": 0, "balance": 0, "paid": False}
    planner: Dict[str, Any] = {"rows": [], "suggested_periods": [], "prompt": ""}

    if active_lease:
        unit = active_lease.unit

        # Source of truth remains lease rent.
        # If you want tenant dashboard to reflect unit rent instantly,
        # change this line to use unit.rent_amount instead.
        effective_rent = float(active_lease.rent_amount or 0)

        unit_info = {
            "id": unit.id if unit else None,
            "number": getattr(unit, "number", None),
            "property_id": getattr(unit, "property_id", None),
            "property_name": getattr(unit.property, "name", None) if unit and unit.property else None,
            "unit_rent_amount": float(getattr(unit, "rent_amount", 0) or 0) if unit else 0,
        }

        lease_info = {
            "id": active_lease.id,
            "rent_amount": effective_rent,
            "start_date": active_lease.start_date.date().isoformat()
            if isinstance(active_lease.start_date, datetime)
            else active_lease.start_date.isoformat(),
            "end_date": active_lease.end_date.date().isoformat()
            if isinstance(active_lease.end_date, datetime) and active_lease.end_date
            else (active_lease.end_date.isoformat() if active_lease.end_date else None),
            "active": int(active_lease.active),
        }

        period = _yyyymm(date.today())
        expected = effective_rent
        received = _sum_allocated_for_period(db, active_lease.id, period)
        balance = round(expected - received, 2)

        this_month = {
            "period": period,
            "expected": expected,
            "received": received,
            "balance": balance if balance > 0 else 0,
            "paid": received >= expected and expected > 0,
            "status": _period_status(expected, received),
        }

        # Make planner also use the same active lease
        planner = _build_period_suggestions(db, active_lease)

    return {
        "tenant": {
            "id": current.id,
            "name": current.name,
            "phone": current.phone,
            "email": current.email,
            "id_number": getattr(current, "id_number", None),
        },
        "unit": unit_info,
        "lease": lease_info,
        "this_month": this_month,
        "planner": planner,
    }