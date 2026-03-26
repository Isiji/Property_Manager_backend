#app/routers/lease_router.py
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from app.dependencies import get_db, get_current_user
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate, LeaseOut
from app.crud import lease_crud
from app import models

router = APIRouter(prefix="/leases", tags=["Leases"])


def _lease_status(lease: models.Lease) -> str:
    return "active" if int(lease.active or 0) == 1 else "inactive"


def _default_terms_text(
    tenant_name: str,
    landlord_name: str,
    property_name: str,
    unit_number: str,
    rent_amount,
    start_date,
    end_date,
) -> str:
    end_label = end_date.strftime("%Y-%m-%d") if end_date else "until terminated by agreement"
    start_label = start_date.strftime("%Y-%m-%d") if start_date else "N/A"

    return f"""
1. This lease agreement is entered into between {landlord_name} (Landlord) and {tenant_name} (Tenant) for occupation of Unit {unit_number} at {property_name}.

2. The tenancy begins on {start_label} and runs until {end_label}, unless otherwise extended, renewed, or lawfully terminated.

3. The monthly rent payable for this unit is KES {float(rent_amount):,.2f}, due on the agreed rent date each month.

4. The tenant shall use the premises only for lawful residential purposes and shall keep the house in good and tenantable condition.

5. The tenant shall promptly report maintenance issues through the PropSmart PMS platform or through the officially provided landlord/manager contacts.

6. The tenant shall not cause nuisance, damage, illegal use of the premises, or unauthorized subletting without written approval from the landlord or manager.

7. The landlord or appointed property manager shall make reasonable efforts to address reported maintenance issues within a practical time depending on the nature of the issue.

8. Payments made through PropSmart PMS, including M-Pesa or other approved channels, shall be treated as valid records once confirmed in the system.

9. Any arrears, penalties, or unpaid service charges may affect the tenant's standing under this lease and may trigger reminders, formal notices, or lawful recovery action.

10. By accepting this lease, the tenant confirms that they have read, understood, and agreed to the terms of occupancy, payment obligations, and use of the PropSmart PMS platform.
""".strip()


def _serialize_lease_details(db: Session, lease: models.Lease) -> dict:
    tenant = (
        db.query(models.Tenant)
        .filter(models.Tenant.id == lease.tenant_id)
        .first()
    )
    unit = (
        db.query(models.Unit)
        .filter(models.Unit.id == lease.unit_id)
        .first()
    )
    prop = (
        db.query(models.Property)
        .filter(models.Property.id == (unit.property_id if unit else 0))
        .first()
        if unit
        else None
    )
    landlord = (
        db.query(models.Landlord)
        .filter(models.Landlord.id == (prop.landlord_id if prop else 0))
        .first()
        if prop
        else None
    )
    manager = (
        db.query(models.PropertyManager)
        .filter(models.PropertyManager.id == (prop.manager_id if prop else 0))
        .first()
        if prop and prop.manager_id
        else None
    )

    tenant_name = tenant.name if tenant else "—"
    landlord_name = landlord.name if landlord else "—"
    property_name = prop.name if prop else "—"
    unit_number = unit.number if unit else "—"

    custom_terms = getattr(lease, "terms_text", None)
    terms_text = custom_terms or _default_terms_text(
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        property_name=property_name,
        unit_number=unit_number,
        rent_amount=lease.rent_amount,
        start_date=lease.start_date,
        end_date=lease.end_date,
    )

    return {
        "id": lease.id,
        "tenant_id": lease.tenant_id,
        "unit_id": lease.unit_id,
        "start_date": lease.start_date.isoformat() if lease.start_date else None,
        "end_date": lease.end_date.isoformat() if lease.end_date else None,
        "rent_amount": float(lease.rent_amount) if lease.rent_amount is not None else None,
        "active": bool(int(lease.active or 0)),
        "status": _lease_status(lease),

        "tenant_name": tenant.name if tenant else "—",
        "tenant_phone": tenant.phone if tenant else "—",
        "tenant_email": tenant.email if tenant else "—",
        "tenant_id_number": getattr(tenant, "id_number", None) if tenant else None,

        "landlord_name": landlord.name if landlord else "—",
        "landlord_phone": landlord.phone if landlord else "—",
        "landlord_email": landlord.email if landlord else "—",

        "property_name": prop.name if prop else "—",
        "property_address": prop.address if prop else "—",
        "property_code": prop.property_code if prop else "—",

        "unit_number": unit.number if unit else "—",

        "manager_name": manager.name if manager else None,
        "manager_company_name": getattr(manager, "company_name", None) if manager else None,
        "manager_phone": getattr(manager, "phone", None) if manager else None,
        "manager_email": getattr(manager, "email", None) if manager else None,

        "terms_text": terms_text,
        "terms_accepted": bool(int(getattr(lease, "terms_accepted", 0) or 0)),
        "terms_accepted_at": (
            getattr(lease, "terms_accepted_at").isoformat()
            if getattr(lease, "terms_accepted_at", None)
            else None
        ),
    }


@router.post("/", response_model=LeaseOut)
def create_lease(payload: LeaseCreate, db: Session = Depends(get_db)):
    try:
        return lease_crud.create_lease(db, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
def my_leases(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = (current or {}).get("role")
    sub = (current or {}).get("sub")

    if not role or not sub:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = int(sub)

    if role == "tenant":
        leases = lease_crud.list_leases_for_tenant(db, user_id)
    elif role == "landlord":
        leases = lease_crud.list_leases_for_landlord(db, user_id)
    elif role in ("property_manager", "manager"):
        leases = lease_crud.list_leases_for_manager(db, user_id)
    else:
        leases = []

    return [_serialize_lease_details(db, lease) for lease in leases]


@router.get("/{lease_id}")
def read_lease(lease_id: int, db: Session = Depends(get_db)):
    lease = lease_crud.get_lease(db, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return _serialize_lease_details(db, lease)


@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease(
    lease_id: int,
    payload: LeaseUpdate,
    db: Session = Depends(get_db),
):
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


@router.post("/{lease_id}/end", response_model=dict)
def end_lease(lease_id: int, payload: dict, db: Session = Depends(get_db)):
    end_date_str = payload.get("end_date")
    try:
        end_date = (
            datetime.fromisoformat(end_date_str)
            if end_date_str
            else datetime.utcnow()
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid end_date format")

    lease = lease_crud.end_lease(db, lease_id, end_date)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    return {
        "ok": True,
        "lease_id": lease.id,
        "ended": lease.end_date.isoformat(),
    }


@router.post("/{lease_id}/accept-terms")
def accept_terms(
    lease_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    if current["role"] != "tenant" or int(current["sub"]) != lease.tenant_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    # These fields should exist in your Lease model for persistence.
    # If not yet added, add them properly in the model + migration.
    if not hasattr(lease, "terms_accepted"):
        raise HTTPException(
            status_code=500,
            detail="Lease terms fields are not yet added to the model/database",
        )

    lease.terms_accepted = 1
    lease.terms_accepted_at = datetime.utcnow()
    db.commit()

    return {"ok": True}


@router.post("/{lease_id}/activate")
def activate_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    if current["role"] != "tenant" or int(current["sub"]) != lease.tenant_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if hasattr(lease, "terms_accepted") and int(lease.terms_accepted or 0) != 1:
        raise HTTPException(status_code=400, detail="Accept terms first")

    lease.active = 1
    db.commit()

    return {"ok": True}


@router.get("/{lease_id}.pdf")
def lease_pdf(
    lease_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    lease: models.Lease = (
        db.query(models.Lease)
        .filter(models.Lease.id == lease_id)
        .first()
    )
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    tenant = (
        db.query(models.Tenant)
        .filter(models.Tenant.id == lease.tenant_id)
        .first()
    )
    unit = (
        db.query(models.Unit)
        .filter(models.Unit.id == lease.unit_id)
        .first()
    )
    prop = (
        db.query(models.Property)
        .filter(models.Property.id == (unit.property_id if unit else 0))
        .first()
        if unit
        else None
    )
    landlord = (
        db.query(models.Landlord)
        .filter(models.Landlord.id == (prop.landlord_id if prop else 0))
        .first()
        if prop
        else None
    )

    if not tenant or not unit or not prop or not landlord:
        raise HTTPException(status_code=400, detail="Related data missing")

    role = current.get("role")
    sub = int(current.get("sub", 0) or 0)

    if role == "tenant" and tenant.id != sub:
        raise HTTPException(status_code=403, detail="Forbidden")

    if role == "landlord" and landlord.id != sub:
        raise HTTPException(status_code=403, detail="Forbidden")

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
    c.drawString(x, y, "Generated by PropSmart PMS")
    c.setFillColor(colors.black)

    y -= 6 * mm
    c.setStrokeColor(colors.lightgrey)
    c.line(x, y, w - x, y)
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Parties")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Landlord: {landlord.name} ({landlord.phone})")
    y -= 6 * mm
    c.drawString(x, y, f"Tenant: {tenant.name} ({tenant.phone})")
    y -= 6 * mm
    c.drawString(x, y, f"Tenant ID No.: {tenant.id_number or '-'}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Premises")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(
        x,
        y,
        f"Property: {prop.name} — {prop.address} [Code: {prop.property_code}]",
    )
    y -= 6 * mm
    c.drawString(x, y, f"Unit: {unit.number}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Term & Rent")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Start Date: {lease.start_date.strftime('%Y-%m-%d')}")
    y -= 6 * mm
    c.drawString(
        x,
        y,
        f"End Date: {(lease.end_date.strftime('%Y-%m-%d') if lease.end_date else 'Open-ended')}",
    )
    y -= 6 * mm
    c.drawString(x, y, f"Monthly Rent: KES {float(lease.rent_amount):,.2f}")

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="lease_{lease_id}.pdf"'
        },
    )