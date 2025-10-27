# app/crud/report_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from typing import Dict, Any, List, Tuple
from app import models

def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end

def landlord_monthly_summary(db: Session, landlord_id: int, year: int, month: int) -> Dict[str, Any]:
    start, end = _month_bounds(year, month)

    props = db.query(models.Property).filter(models.Property.landlord_id == landlord_id).all()
    prop_ids = [p.id for p in props]
    if not prop_ids:
        return {
            "landlord_id": landlord_id, "year": year, "month": month,
            "expected_total": 0.0, "received_total": 0.0, "pending_total": 0.0,
            "properties": [], "arrears": []
        }

    units = db.query(models.Unit).filter(models.Unit.property_id.in_(prop_ids)).all()
    unit_ids = [u.id for u in units]
    leases = db.query(models.Lease).filter(
        models.Lease.unit_id.in_(unit_ids),
        models.Lease.active == 1
    ).all()
    leases_by_unit = {l.unit_id: l for l in leases}

    expected_by_unit: Dict[int, float] = {}
    for u in units:
        if u.id in leases_by_unit:
            expected_by_unit[u.id] = expected_by_unit.get(u.id, 0.0) + float(u.rent_amount or 0)

    payments = []
    if unit_ids:
        payments = db.query(
            models.Payment.unit_id,
            func.coalesce(func.sum(models.Payment.amount), 0)
        ).filter(
            models.Payment.unit_id.in_(unit_ids),
            and_(models.Payment.created_at >= start, models.Payment.created_at < end)
        ).group_by(models.Payment.unit_id).all()

    paid_by_unit = {u: 0.0 for u in unit_ids}
    for unit_id, total in payments:
        paid_by_unit[int(unit_id)] = float(total or 0)

    units_by_property: Dict[int, List[models.Unit]] = {}
    for u in units:
        units_by_property.setdefault(u.property_id, []).append(u)

    properties_summary: List[Dict[str, Any]] = []
    expected_total = 0.0
    received_total = 0.0

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

    # Arrears
    tenant_ids = [l.tenant_id for l in leases]
    payments_by_tenant = {}
    if tenant_ids:
        q = db.query(
            models.Payment.tenant_id,
            func.coalesce(func.sum(models.Payment.amount), 0)
        ).filter(
            models.Payment.tenant_id.in_(tenant_ids),
            and_(models.Payment.created_at >= start, models.Payment.created_at < end)
        ).group_by(models.Payment.tenant_id).all()
        payments_by_tenant = {int(tid): float(total or 0) for tid, total in q}

    expected_by_tenant: Dict[int, float] = {}
    unit_by_id = {u.id: u for u in units}
    for l in leases:
        u = unit_by_id.get(l.unit_id)
        if not u:
            continue
        expected_by_tenant[l.tenant_id] = expected_by_tenant.get(l.tenant_id, 0.0) + float(u.rent_amount or 0)

    tenants = db.query(models.Tenant).filter(models.Tenant.id.in_(tenant_ids)).all() if tenant_ids else []
    tenant_map = {t.id: t for t in tenants}

    arrears_list: List[Dict[str, Any]] = []
    for tid, exp in expected_by_tenant.items():
        paid = payments_by_tenant.get(tid, 0.0)
        bal = exp - paid
        if bal > 0.001:
            t = tenant_map.get(tid)
            arrears_list.append({
                "tenant_id": tid,
                "tenant_name": t.name if t else "Unknown",
                "phone": t.phone if t else None,
                "expected": round(exp, 2),
                "paid": round(paid, 2),
                "balance": round(bal, 2),
            })
    arrears_list.sort(key=lambda x: x["balance"], reverse=True)

    return {
        "landlord_id": landlord_id, "year": year, "month": month,
        "expected_total": round(expected_total, 2),
        "received_total": round(received_total, 2),
        "pending_total": round(max(expected_total - received_total, 0.0), 2),
        "properties": properties_summary,
        "arrears": arrears_list,
    }

def property_monthly_summary(db: Session, property_id: int, year: int, month: int) -> Dict[str, Any]:
    start, end = _month_bounds(year, month)

    p = db.query(models.Property).filter(models.Property.id == property_id).first()
    if not p:
        return {"property_id": property_id, "year": year, "month": month,
                "expected": 0.0, "received": 0.0, "pending": 0.0}

    units = db.query(models.Unit).filter(models.Unit.property_id == property_id).all()
    unit_ids = [u.id for u in units]
    leases = db.query(models.Lease).filter(models.Lease.unit_id.in_(unit_ids), models.Lease.active == 1).all()
    leases_by_unit = {l.unit_id: l for l in leases}

    expected = 0.0
    for u in units:
        if u.id in leases_by_unit:
            expected += float(u.rent_amount or 0)

    received = 0.0
    if unit_ids:
        q = db.query(func.coalesce(func.sum(models.Payment.amount), 0)).filter(
            models.Payment.unit_id.in_(unit_ids),
            and_(models.Payment.created_at >= start, models.Payment.created_at < end)
        ).scalar()
        received = float(q or 0.0)

    return {
        "property_id": p.id,
        "name": p.name,
        "year": year, "month": month,
        "expected": round(expected, 2),
        "received": round(received, 2),
        "pending": round(max(expected - received, 0.0), 2)
    }

def landlord_monthly_csv(db: Session, landlord_id: int, year: int, month: int) -> str:
    data = landlord_monthly_summary(db, landlord_id, year, month)
    lines = []
    lines.append("Landlord ID,Year,Month,Expected,Received,Pending")
    lines.append(f"{data['landlord_id']},{data['year']},{data['month']},{data['expected_total']},{data['received_total']},{data['pending_total']}")
    lines.append("")  # blank
    lines.append("Property,Expected,Received,Pending")
    for r in data["properties"]:
        lines.append(f"{r['name']},{r['expected']},{r['received']},{r['pending']}")
    lines.append("")  # blank
    lines.append("Tenant,Phone,Expected,Paid,Balance")
    for a in data["arrears"]:
        name = (a["tenant_name"] or "").replace(",", " ")
        phone = (a["phone"] or "")
        lines.append(f"{name},{phone},{a['expected']},{a['paid']},{a['balance']}")
    return "\n".join(lines)

def landlord_reminder_recipients(db: Session, landlord_id: int, year: int, month: int) -> List[Dict[str, Any]]:
    data = landlord_monthly_summary(db, landlord_id, year, month)
    return data.get("arrears", [])
