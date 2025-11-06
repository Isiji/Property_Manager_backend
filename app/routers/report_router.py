from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import io
import csv
from openpyxl import Workbook

from app.dependencies import get_db, get_current_user, role_required
from app import models

router = APIRouter(prefix="/reports", tags=["Reports"])

def _yyyymm(year: int, month: int) -> str:
    return f"{year}-{str(month).zfill(2)}"

@router.get("/landlord/{landlord_id}/monthly-summary")
def landlord_monthly_summary(
    landlord_id: int,
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    # auth: only this landlord or admin/manager
    role = current.get("role")
    user_id = int(current.get("sub", 0))
    if role == "landlord" and user_id != landlord_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    period = _yyyymm(year, month)

    # properties owned by landlord
    props = db.query(models.Property).filter(models.Property.landlord_id == landlord_id).all()
    prop_ids = [p.id for p in props]

    # expected: sum of active lease rent_amount for period (assume constant monthly rent)
    active_leases = (
        db.query(models.Lease)
        .filter(models.Lease.active == 1)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(models.Unit.property_id.in__(prop_ids))
        .all()
    )

    expected_total = 0.0
    property_rows: Dict[int, Dict[str, Any]] = {p.id: {"name": p.name, "expected": 0.0, "received": 0.0, "pending": 0.0} for p in props}

    for l in active_leases:
        amt = float(l.rent_amount or 0)
        expected_total += amt
        unit = db.query(models.Unit).filter(models.Unit.id == l.unit_id).first()
        if unit and unit.property_id in property_rows:
            property_rows[unit.property_id]["expected"] += amt

    # received for the period
    pays = (
        db.query(models.Payment)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(models.Unit.property_id.in__(prop_ids))
        .filter(models.Payment.period == period)
        .all()
    )

    received_total = 0.0
    for p in pays:
        amt = float(p.amount or 0)
        received_total += amt
        lease = db.query(models.Lease).filter(models.Lease.id == p.lease_id).first()
        if lease:
            unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
            if unit and unit.property_id in property_rows:
                property_rows[unit.property_id]["received"] += amt

    # pending
    for pid, row in property_rows.items():
        row["pending"] = round(float(row["expected"]) - float(row["received"]), 2)

    # arrears list (top)
    arrears: List[Dict[str, Any]] = []
    for l in active_leases:
        expected = float(l.rent_amount or 0)
        paid = 0.0
        for p in pays:
            if p.lease_id == l.id:
                paid += float(p.amount or 0)
        bal = round(expected - paid, 2)
        if bal > 0.0:
            t = db.query(models.Tenant).filter(models.Tenant.id == l.tenant_id).first()
            if t:
                arrears.append({
                    "tenant_name": t.name,
                    "phone": t.phone,
                    "expected": expected,
                    "paid": paid,
                    "balance": bal,
                    "lease_id": l.id,
                })

    arrears.sort(key=lambda x: x["balance"], reverse=True)

    return {
        "expected_total": expected_total,
        "received_total": received_total,
        "pending_total": round(expected_total - received_total, 2),
        "properties": [
            {"name": v["name"], "expected": v["expected"], "received": v["received"], "pending": v["pending"]}
            for v in property_rows.values()
        ],
        "arrears": arrears,
    }

@router.get("/landlord/{landlord_id}/monthly-summary.csv")
def landlord_monthly_summary_csv(
    landlord_id: int,
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user)
):
    data = landlord_monthly_summary(landlord_id, year, month, db, current)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Expected Total", data["expected_total"]])
    writer.writerow(["Received Total", data["received_total"]])
    writer.writerow(["Pending Total", data["pending_total"]])
    writer.writerow([])
    writer.writerow(["Property", "Expected", "Received", "Pending"])
    for r in data["properties"]:
        writer.writerow([r["name"], r["expected"], r["received"], r["pending"]])
    writer.writerow([])
    writer.writerow(["Tenant", "Phone", "Expected", "Paid", "Balance", "Lease ID"])
    for a in data["arrears"]:
        writer.writerow([a["tenant_name"], a["phone"], a["expected"], a["paid"], a["balance"], a["lease_id"]])
    content = output.getvalue().encode("utf-8")
    return Response(content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=monthly_summary.csv"})

@router.get("/landlord/{landlord_id}/monthly-summary.xlsx")
def landlord_monthly_summary_xlsx(
    landlord_id: int,
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user)
):
    data = landlord_monthly_summary(landlord_id, year, month, db, current)
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    ws.append(["Metric", "Value"])
    ws.append(["Expected Total", data["expected_total"]])
    ws.append(["Received Total", data["received_total"]])
    ws.append(["Pending Total", data["pending_total"]])

    ws = wb.createSheet(title="Properties")
    ws.append(["Property", "Expected", "Received", "Pending"])
    for r in data["properties"]:
        ws.append([r["name"], r["expected"], r["received"], r["pending"]])

    ws = wb.createSheet(title="Arrears")
    ws.append(["Tenant", "Phone", "Expected", "Paid", "Balance", "Lease ID"])
    for a in data["arrears"]:
        ws.append([a["tenant_name"], a["phone"], a["expected"], a["paid"], a["balance"], a["lease_id"]])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=monthly_summary.xlsx"}
    )
