# app/routers/bulk_router.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
import csv
from io import StringIO
from typing import Optional
from app.dependencies import get_db
from app import models

router = APIRouter(prefix="/bulk", tags=["Bulk Import"])

@router.post("/units")
async def import_units_csv(
    property_id: int = Query(..., description="Property to attach units to"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    required = {"number", "rent_amount"}
    if not required.issubset(set([c.strip() for c in reader.fieldnames or []])):
        raise HTTPException(status_code=400, detail="CSV must have headers: number,rent_amount")

    created, updated = 0, 0
    for row in reader:
        number = (row.get("number") or "").strip()
        rent = (row.get("rent_amount") or "").strip()
        if not number or not rent:
            continue
        try:
            rent_val = float(rent)
        except:
            continue

        unit = db.query(models.Unit).filter(
            models.Unit.property_id == property_id,
            models.Unit.number == number
        ).first()
        if unit:
            unit.rent_amount = rent_val
            updated += 1
        else:
            unit = models.Unit(number=number, rent_amount=rent_val, property_id=property_id, occupied=0)
            db.add(unit)
            created += 1
    db.commit()
    return {"ok": True, "created": created, "updated": updated}

@router.post("/tenants")
async def import_tenants_csv(
    property_id: int = Query(..., description="Property for these tenants"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    required = {"name", "phone"}
    if not required.issubset(set([c.strip() for c in reader.fieldnames or []])):
        raise HTTPException(status_code=400, detail="CSV must have headers: name,phone[,email][,unit_number]")

    created, updated = 0, 0
    for row in reader:
        name = (row.get("name") or "").strip()
        phone = (row.get("phone") or "").strip()
        email = (row.get("email") or None)
        unit_number = (row.get("unit_number") or "").strip()

        if not name or not phone:
            continue

        unit_id: Optional[int] = None
        if unit_number:
            unit = db.query(models.Unit).filter(
                models.Unit.property_id == property_id,
                models.Unit.number == unit_number
            ).first()
            if unit:
                unit_id = unit.id

        # unique by phone (your DB has unique index)
        t = db.query(models.Tenant).filter(models.Tenant.phone == phone).first()
        if t:
            t.name = name
            t.email = email
            if unit_id:
                t.unit_id = unit_id
            updated += 1
        else:
            t = models.Tenant(name=name, phone=phone, email=email, property_id=property_id, unit_id=unit_id)
            db.add(t)
            created += 1
    db.commit()
    return {"ok": True, "created": created, "updated": updated}
