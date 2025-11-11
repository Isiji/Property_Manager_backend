from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate, LeaseOut
from app.crud import lease_crud
from app import models

# PDF (ReportLab)
from io import BytesIO
from fastapi import Response
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors

router = APIRouter(prefix="/leases", tags=["Leases"])


@router.post("/", response_model=LeaseOut)
def create_lease(payload: LeaseCreate, db: Session = Depends(get_db)):
    try:
        lease = lease_crud.create_lease(db, payload)
        return lease
    except Exception as e:
        print("❌ create_lease error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lease_id}", response_model=LeaseOut)
def read_lease(lease_id: int, db: Session = Depends(get_db)):
    lease = lease_crud.get_lease(db, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease(lease_id: int, payload: LeaseUpdate, db: Session = Depends(get_db)):
    lease = lease_crud.update_lease(db, lease_id, payload)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.delete("/{lease_id}", response_model=dict)
def delete_lease(lease_id: int, db: Session = Depends(get_db)):
    ok = lease_crud.delete_lease(db, lease_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lease not found")
    return {"ok": True}


# ---------- NEW: Tenant's active lease ----------
@router.get("/me", response_model=Optional[LeaseOut])
def my_active_lease(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """
    Returns the current tenant's active lease or null.
    Avoids 404/422 so the frontend can just check for null.
    """
    if current.get("role") != "tenant":
        raise HTTPException(status_code=403, detail="Tenant role required")
    tenant_id = int(current.get("sub", 0) or 0)
    if tenant_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")

    lease: models.Lease | None = (
        db.query(models.Lease)
        .filter(models.Lease.tenant_id == tenant_id, models.Lease.active == 1)
        .order_by(models.Lease.id.desc())
        .first()
    )
    if not lease:
        return None

    # Ensure date-only to satisfy your LeaseOut schema
    start_date = lease.start_date.date() if isinstance(lease.start_date, datetime) else lease.start_date
    end_date = lease.end_date.date() if isinstance(lease.end_date, datetime) and lease.end_date else None

    return LeaseOut(
        id=lease.id,
        tenant_id=lease.tenant_id,
        unit_id=lease.unit_id,
        start_date=start_date or date.today(),
        end_date=end_date,
        rent_amount=float(lease.rent_amount) if lease.rent_amount is not None else None,
        active=int(lease.active or 0),
    )


# ---------- End Lease ----------
@router.post("/{lease_id}/end", response_model=dict)
def end_lease(lease_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Body: {"end_date":"YYYY-MM-DD"} optional; defaults to today
    - Sets lease.end_date
    - Sets lease.active = 0
    - Marks unit.occupied = 0
    """
    end_date_str = payload.get("end_date")
    try:
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.utcnow()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid end_date format")

    lease = lease_crud.end_lease(db, lease_id, end_date)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return {"ok": True, "lease_id": lease.id, "ended": lease.end_date.isoformat()}


# ---------- Lease PDF ----------
@router.get("/{lease_id}.pdf")
def lease_pdf(
    lease_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """
    Downloads an autofilled Lease PDF for the lease.
    AuthZ: tenant (own lease), landlord/manager/admin of the property.
    """
    lease: models.Lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == lease.tenant_id).first()
    unit = db.query(models.Unit).filter(models.Unit.id == lease.unit_id).first()
    prop = db.query(models.Property).filter(models.Property.id == (unit.property_id if unit else 0)).first() if unit else None
    landlord = db.query(models.Landlord).filter(models.Landlord.id == (prop.landlord_id if prop else 0)).first() if prop else None

    if not tenant or not unit or not prop or not landlord:
        raise HTTPException(status_code=400, detail="Related data missing")

    # AuthZ
    role = current.get("role")
    sub = int(current.get("sub", 0) or 0)
    if role == "tenant":
        if tenant.id != sub:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif role == "landlord":
        if landlord.id != sub:
            raise HTTPException(status_code=403, detail="Forbidden")
    # admin/manager allowed

    # Build PDF
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x = 20 * mm
    y = h - 25 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Residential Lease Agreement")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.grey)
    c.drawString(x, y, "Generated by Property Manager")
    c.setFillColor(colors.black)

    y -= 6 * mm
    c.setStrokeColor(colors.lightgrey)
    c.line(x, y, w - x, y)
    y -= 10 * mm

    # Parties
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Parties")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Landlord: {landlord.name}  ({landlord.phone})")
    y -= 6 * mm
    c.drawString(x, y, f"Tenant:   {tenant.name}  ({tenant.phone})")
    y -= 6 * mm
    c.drawString(x, y, f"Tenant ID No.: {tenant.id_number or '-'}")
    y -= 10 * mm

    # Premises
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Premises")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Property: {prop.name} — {prop.address}  [Code: {prop.property_code}]")
    y -= 6 * mm
    c.drawString(x, y, f"Unit: {unit.number}")
    y -= 10 * mm

    # Term & Rent
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Term & Rent")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Start Date: {lease.start_date.strftime('%Y-%m-%d')}")
    y -= 6 * mm
    c.drawString(x, y, f"End Date:   {(lease.end_date.strftime('%Y-%m-%d') if lease.end_date else 'Open-ended')}")
    y -= 6 * mm
    c.drawString(x, y, f"Monthly Rent: KES {float(lease.rent_amount):,.2f}")
    y -= 10 * mm

    # Basic terms
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Terms (Summary)")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    lines = [
        "1) Rent is due by the 5th day of each month unless otherwise agreed.",
        "2) Late payments may attract penalties as per property policy.",
        "3) Tenant agrees to keep the premises in good condition.",
        "4) Utilities and service charges are settled as agreed with the landlord/manager.",
    ]
    for ln in lines:
        c.drawString(x, y, ln)
        y -= 6 * mm

    # Footer
    y -= 8 * mm
    c.setStrokeColor(colors.lightgrey)
    c.line(x, 25 * mm, w - x, 25 * mm)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString(x, 20 * mm, "This is a system-generated lease summary. Full T&Cs may be provided separately.")
    c.setFillColor(colors.black)

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename=\"lease_{lease_id}.pdf\"'}
    )
