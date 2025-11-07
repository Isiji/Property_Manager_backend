# app/routers/reports_property_status_router.py
from __future__ import annotations

from typing import Dict, Any, List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app import models

router = APIRouter(prefix="/reports/property", tags=["Reports: Property Status"])

def _as_float(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except Exception:
        return 0.0

@router.get("/{property_id}/status")
def property_status_by_month(
    property_id: int,
    period: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    current: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns per-unit monthly status for a property:
      items: [
        {
          unit_id, unit_number,
          lease_id, tenant_id, tenant_name, tenant_phone,
          expected, amount_paid, amount_due,
          status,    # 'paid' if any row is paid else 'pending' (for the month)
          paid       # boolean convenience flag for UI
        },
        ...
      ]
    """
    # Auth guard: landlords/managers/admins only
    role = current.get("role")
    sub_id = int(current.get("sub", 0) or 0)

    if role == "tenant":
        raise HTTPException(status_code=403, detail="Tenants cannot access property status")

    # If landlord, ensure they own the property
    if role == "landlord":
        prop = (
            db.query(models.Property)
            .filter(models.Property.id == property_id)
            .first()
        )
        if not prop or int(prop.landlord_id or 0) != sub_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    # Collect active leases for units in the property
    units: List[models.Unit] = (
        db.query(models.Unit)
        .filter(models.Unit.property_id == property_id)
        .all()
    )

    # Preload all active leases for these units
    unit_ids = [u.id for u in units]
    leases: List[models.Lease] = []
    if unit_ids:
        leases = (
            db.query(models.Lease)
            .filter(models.Lease.active == 1)
            .filter(models.Lease.unit_id.in_(unit_ids))
            .all()
        )

    # Map for quick lookup
    lease_by_unit: Dict[int, models.Lease] = {l.unit_id: l for l in leases}

    items: List[Dict[str, Any]] = []

    for u in units:
        l: Optional[models.Lease] = lease_by_unit.get(u.id)
        if not l:
            # vacant unit
            items.append({
                "unit_id": u.id,
                "unit_number": u.number,
                "lease_id": None,
                "tenant_id": None,
                "tenant_name": None,
                "tenant_phone": None,
                "expected": 0.0,
                "amount_paid": 0.0,
                "amount_due": 0.0,
                "status": "pending",
                "paid": False,
            })
            continue

        expected = _as_float(l.rent_amount)

        # Payments for this lease & this month
        pays: List[models.Payment] = (
            db.query(models.Payment)
            .filter(models.Payment.lease_id == l.id)
            .filter(models.Payment.period == period)
            .all()
        )

        # Determine if any row is explicitly marked paid
        any_paid_row = any((p.status == models.PaymentStatus.paid) for p in pays)

        # Total amount paid (you may choose to sum only rows with status='paid';
        # here we sum all rows to be forgiving with reconciliations)
        amount_paid = _as_float(sum(_as_float(p.amount) for p in pays))

        # Final status/flag rule (robust):
        # - paid if there exists a paid row, OR sum >= expected
        paid_flag = any_paid_row or (amount_paid >= expected if expected > 0 else False)
        status = "paid" if paid_flag else "pending"

        # Amount due (never negative)
        amount_due = max(0.0, round(expected - amount_paid, 2))

        # Tenant summary
        t = db.query(models.Tenant).filter(models.Tenant.id == l.tenant_id).first()

        items.append({
            "unit_id": u.id,
            "unit_number": u.number,
            "lease_id": l.id,
            "tenant_id": t.id if t else None,
            "tenant_name": t.name if t else None,
            "tenant_phone": t.phone if t else None,
            "expected": round(expected, 2),
            "amount_paid": round(amount_paid, 2),
            "amount_due": amount_due,
            "status": status,
            "paid": paid_flag,
        })

    # Optional totals for header widgets
    total_expected = round(sum(_as_float(it["expected"]) for it in items), 2)
    total_paid     = round(sum(_as_float(it["amount_paid"]) for it in items), 2)
    total_due      = round(max(0.0, total_expected - total_paid), 2)

    return {
        "property_id": property_id,
        "period": period,
        "totals": {
            "expected": total_expected,
            "received": total_paid,
            "pending": total_due,
        },
        "items": items,
    }
