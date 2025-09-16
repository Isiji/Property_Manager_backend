# app/routers/bulk_upload.py
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd
from .. import models
from ..dependencies import get_db
from io import BytesIO
import re

router = APIRouter(prefix="/bulk", tags=["Bulk Upload"])

# ----------------------------
# Utils
# ----------------------------
def is_valid_email(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None


# ----------------------------
# Tenants Bulk Upload
# ----------------------------
@router.post("/tenants/")
async def bulk_upload_tenants(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="File must be .csv or .xlsx")

    contents = await file.read()
    if file.filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(contents))
    else:
        df = pd.read_excel(BytesIO(contents))

    required_cols = {"name", "email", "phone"}
    if not required_cols.issubset(df.columns):
        raise HTTPException(status_code=400, detail=f"Missing required columns: {required_cols}")

    errors = []
    created_tenants = []

    for i, row in df.iterrows():
        name, email, phone = row["name"], row["email"], row["phone"]

        # Basic validations
        if not name or pd.isna(name):
            errors.append(f"Row {i+1}: Name is required")
            continue
        if not is_valid_email(str(email)):
            errors.append(f"Row {i+1}: Invalid email '{email}'")
            continue

        # Check duplicates in DB
        existing = db.query(models.Tenant).filter(
            (models.Tenant.email == email) | (models.Tenant.phone == phone)
        ).first()
        if existing:
            errors.append(f"Row {i+1}: Tenant with email/phone already exists")
            continue

        # Create object
        tenant = models.Tenant(name=name, email=email, phone=phone)
        db.add(tenant)
        created_tenants.append(tenant)

    # Save only if no fatal errors
    if errors:
        return {"status": "failed", "errors": errors}

    db.commit()
    return {"status": "success", "inserted": len(created_tenants), "tenants": [t.name for t in created_tenants]}


# ----------------------------
# Units Bulk Upload
# ----------------------------
@router.post("/units/")
async def bulk_upload_units(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="File must be .csv or .xlsx")

    contents = await file.read()
    if file.filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(contents))
    else:
        df = pd.read_excel(BytesIO(contents))

    required_cols = {"number", "rent_amount", "property_id"}
    if not required_cols.issubset(df.columns):
        raise HTTPException(status_code=400, detail=f"Missing required columns: {required_cols}")

    errors = []
    created_units = []

    for i, row in df.iterrows():
        number, rent_amount, property_id = row["number"], row["rent_amount"], row["property_id"]

        if not number or pd.isna(number):
            errors.append(f"Row {i+1}: Unit number is required")
            continue
        try:
            rent_amount = float(rent_amount)
            if rent_amount <= 0:
                raise ValueError
        except Exception:
            errors.append(f"Row {i+1}: Invalid rent_amount '{rent_amount}'")
            continue

        property_exists = db.query(models.Property).filter(models.Property.id == property_id).first()
        if not property_exists:
            errors.append(f"Row {i+1}: Property ID {property_id} does not exist")
            continue

        # Check if unit already exists under this property
        existing = db.query(models.Unit).filter(
            models.Unit.number == number, models.Unit.property_id == property_id
        ).first()
        if existing:
            errors.append(f"Row {i+1}: Unit {number} already exists in Property {property_id}")
            continue

        # Create object
        unit = models.Unit(number=number, rent_amount=rent_amount, property_id=property_id)
        db.add(unit)
        created_units.append(unit)

    if errors:
        return {"status": "failed", "errors": errors}

    db.commit()
    return {"status": "success", "inserted": len(created_units), "units": [u.number for u in created_units]}
