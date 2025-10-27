from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.payment_model import Payment, ServiceCharge
from app.models.property_models import Property, Unit
from datetime import date
from typing import List, Dict, Any
from app import models


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end

def landlord_monthly_summary(db: Session, landlord_id: int, year: int, month: int) -> Dict[str, Any]:
    """
    Expected: sum of unit.rent_amount for units with ACTIVE lease in the period.
    Received: sum of payments for those units/tenants in [start,end).
    Pending: Expected - Received
    Also returns per-property breakdown and a simple arrears (top debtors) list.
    """
    start, end = _month_bounds(year, month)

    # Properties owned by landlord
    props = db.query(models.Property).filter(models.Property.landlord_id == landlord_id).all()
    prop_ids = [p.id for p in props]
    if not prop_ids:
        return {
            "landlord_id": landlord_id,
            "year": year,
            "month": month,
            "expected_total": 0.0,
            "received_total": 0.0,
            "pending_total": 0.0,
            "properties": [],
            "arrears": [],
        }

    # Units under those properties
    units = db.query(models.Unit).filter(models.Unit.property_id.in_(prop_ids)).all()
    unit_ids = [u.id for u in units]

    # Active leases in the month (active == 1), optionally bounded by start/end if you track start_date/end_date
    active_leases = db.query(models.Lease).filter(
        models.Lease.unit_id.in_(unit_ids),
        models.Lease.active == 1
    ).all()
    leases_by_unit = {l.unit_id: l for l in active_leases}

    # Expected per unit = unit.rent_amount if there's an active lease
    expected_by_unit: Dict[int, float] = {}
    for u in units:
        if u.id in leases_by_unit:
            amt = float(u.rent_amount or 0)
            expected_by_unit[u.id] = expected_by_unit.get(u.id, 0.0) + amt

    # Payments within month for those units
    if unit_ids:
        payments = db.query(
            models.Payment.unit_id,
            func.coalesce(func.sum(models.Payment.amount), 0)
        ).filter(
            models.Payment.unit_id.in_(unit_ids),
            and_(models.Payment.created_at >= start, models.Payment.created_at < end)
        ).group_by(models.Payment.unit_id).all()
    else:
        payments = []

    paid_by_unit: Dict[int, float] = {u: 0.0 for u in unit_ids}
    for unit_id, total in payments:
        paid_by_unit[int(unit_id)] = float(total or 0)

    # Per-property aggregation
    properties_summary: List[Dict[str, Any]] = []
    expected_total, received_total = 0.0, 0.0

    # Pre-index units by property
    units_by_property: Dict[int, List[models.Unit]] = {}
    for u in units:
        units_by_property.setdefault(u.property_id, []).append(u)

    for p in props:
        exp_p, rec_p = 0.0, 0.0
        for u in units_by_property.get(p.id, []):
            exp_p += expected_by_unit.get(u.id, 0.0)
            rec_p += paid_by_unit.get(u.id, 0.0)

        properties_summary.append({
            "property_id": p.id,
            "name": p.name,
            "expected": round(exp_p, 2),
            "received": round(rec_p, 2),
            "pending": round(max(exp_p - rec_p, 0.0), 2),
        })
        expected_total += exp_p
        received_total += rec_p

    # Arrears (top debtors) — compute per-tenant balance
    # For each active lease -> tenant owes rent of that unit for the month minus payments from that tenant in month.
    arrears_list: List[Dict[str, Any]] = []
    tenant_ids = [l.tenant_id for l in active_leases]
    if tenant_ids:
        payments_by_tenant = db.query(
            models.Payment.tenant_id,
            func.coalesce(func.sum(models.Payment.amount), 0)
        ).filter(
            models.Payment.tenant_id.in_(tenant_ids),
            and_(models.Payment.created_at >= start, models.Payment.created_at < end)
        ).group_by(models.Payment.tenant_id).all()
        paid_tenant_map = {int(tid): float(total or 0) for tid, total in payments_by_tenant}
    else:
        paid_tenant_map = {}

    # Map tenant -> expected (sum of his/her units; usually one)
    expected_by_tenant: Dict[int, float] = {}
    for l in active_leases:
        unit = next((u for u in units if u.id == l.unit_id), None)
        if not unit:
            continue
        expected_by_tenant[l.tenant_id] = expected_by_tenant.get(l.tenant_id, 0.0) + float(unit.rent_amount or 0)

    # Build arrears rows (only those who still owe)
    tenants = db.query(models.Tenant).filter(models.Tenant.id.in_(tenant_ids)).all()
    tenant_map = {t.id: t for t in tenants}
    for tid, exp in expected_by_tenant.items():
        paid = paid_tenant_map.get(tid, 0.0)
        bal = exp - paid
        if bal > 0.001:  # owes
            t = tenant_map.get(tid)
            arrears_list.append({
                "tenant_id": tid,
                "tenant_name": t.name if t else "Unknown",
                "phone": t.phone if t else None,
                "expected": round(exp, 2),
                "paid": round(paid, 2),
                "balance": round(bal, 2),
            })

    # Sort arrears by highest balance
    arrears_list.sort(key=lambda x: x["balance"], reverse=True)

    pending_total = max(expected_total - received_total, 0.0)

    return {
        "landlord_id": landlord_id,
        "year": year,
        "month": month,
        "expected_total": round(expected_total, 2),
        "received_total": round(received_total, 2),
        "pending_total": round(pending_total, 2),
        "properties": properties_summary,
        "arrears": arrears_list
    }
# ---------------- RENT COLLECTION ----------------
def get_rent_collection_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            func.coalesce(func.sum(Payment.amount), 0).label("total_rent_collected"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .join(Payment, Payment.unit_id == Unit.id, isouter=True)
        .group_by(Property.id, Property.name)
        .all()
    )
    return results


# ---------------- SERVICE CHARGES ----------------
def get_service_charge_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            ServiceCharge.service_type,
            func.coalesce(func.sum(ServiceCharge.amount), 0).label("total_amount"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .join(ServiceCharge, ServiceCharge.unit_id == Unit.id, isouter=True)
        .group_by(Property.id, Property.name, ServiceCharge.service_type)
        .all()
    )
    return results


# ---------------- OCCUPANCY ----------------
def get_occupancy_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            func.count(Unit.id).label("total_units"),
            func.sum(func.case([(Unit.is_occupied == True, 1)], else_=0)).label("occupied_units"),
            func.sum(func.case([(Unit.is_occupied == False, 1)], else_=0)).label("vacant_units"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .group_by(Property.id, Property.name)
        .all()
    )

    summaries = []
    for r in results:
        occupancy_rate = (r.occupied_units / r.total_units * 100) if r.total_units > 0 else 0
        summaries.append({
            "property_id": r.property_id,
            "property_name": r.property_name,
            "total_units": r.total_units,
            "occupied_units": r.occupied_units,
            "vacant_units": r.vacant_units,
            "occupancy_rate": round(occupancy_rate, 2),
        })
    return summaries


