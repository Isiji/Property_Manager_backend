from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app import models

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

router = APIRouter(prefix="/payments", tags=["Payments: Receipts"])


def _safe_decimal(v) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except Exception:
        return Decimal("0")


def _fmt_money(v) -> str:
    amt = _safe_decimal(v)
    return f"KES {amt:,.2f}"


def _fmt_datetime(dt_value) -> tuple[str, str]:
    if not dt_value:
        dt_value = datetime.utcnow()

    if hasattr(dt_value, "strftime"):
        return dt_value.strftime("%Y-%m-%d"), dt_value.strftime("%H:%M:%S")

    return "-", "-"


def _receipt_number(payment: models.Payment, receipt: Optional[models.PaymentReceipt] = None) -> str:
    if receipt and getattr(receipt, "receipt_number", None):
        return receipt.receipt_number

    base_date = getattr(payment, "paid_date", None) or getattr(payment, "created_at", None) or datetime.utcnow()
    if hasattr(base_date, "strftime"):
        return f"PM-{payment.id:06d}-{base_date.strftime('%Y%m%d')}"
    return f"PM-{payment.id:06d}"


def _get_allocations(db: Session, payment: models.Payment, receipt: Optional[models.PaymentReceipt] = None) -> list[dict]:
    allocations: list[dict] = []

    # 1. Prefer actual PaymentAllocation rows
    payment_allocations = getattr(payment, "allocations", None)
    if payment_allocations:
        for a in payment_allocations:
            allocations.append({
                "period": getattr(a, "period", "-"),
                "amount_applied": _safe_decimal(getattr(a, "amount_applied", 0)),
            })
        if allocations:
            return allocations

    # 2. Fallback to receipt.allocations_json
    if receipt and getattr(receipt, "allocations_json", None):
        try:
            raw = json.loads(receipt.allocations_json)
            if isinstance(raw, list):
                for row in raw:
                    if isinstance(row, dict):
                        allocations.append({
                            "period": str(row.get("period") or "-"),
                            "amount_applied": _safe_decimal(
                                row.get("amount_applied", row.get("amount", 0))
                            ),
                        })
        except Exception:
            pass

    if allocations:
        return allocations

    # 3. Legacy fallback to single period from Payment / Receipt
    legacy_period = (
        getattr(payment, "period", None)
        or (getattr(receipt, "period", None) if receipt else None)
        or "-"
    )
    allocations.append({
        "period": legacy_period,
        "amount_applied": _safe_decimal(getattr(payment, "amount", 0)),
    })
    return allocations


def _ensure_receipt(db: Session, payment: models.Payment) -> Optional[models.PaymentReceipt]:
    receipt = (
        db.query(models.PaymentReceipt)
        .filter(models.PaymentReceipt.payment_id == payment.id)
        .first()
    )
    if receipt:
        return receipt

    # Auto-create receipt only for paid payments
    status_value = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
    if status_value != "paid":
        return None

    try:
        from app.services.payment_handler import handle_payment_success
        receipt = handle_payment_success(db, payment)
        return receipt
    except Exception:
        return None


def _build_pdf_bytes(
    payment: models.Payment,
    receipt: Optional[models.PaymentReceipt],
    tenant: Optional[models.Tenant],
    unit: Optional[models.Unit],
    lease: Optional[models.Lease],
    property_: Optional[models.Property],
    landlord: Optional[models.Landlord],
    manager: Optional[object],
    allocations: list[dict],
) -> bytes:
    amount = _safe_decimal(getattr(payment, "amount", 0))
    reference = getattr(payment, "reference", None) or (getattr(receipt, "payment_reference", None) if receipt else None) or "-"
    payment_method = (
        getattr(payment, "payment_method", None)
        or (getattr(receipt, "payment_method", None) if receipt else None)
        or "M-Pesa"
    )
    status = payment.status.value if hasattr(payment.status, "value") else str(payment.status)

    dt_source = getattr(payment, "created_at", None) or getattr(receipt, "issued_at", None) or datetime.utcnow()
    paid_date_str, paid_time_str = _fmt_datetime(dt_source)

    if getattr(payment, "paid_date", None):
        try:
            paid_date_str = payment.paid_date.strftime("%Y-%m-%d")
        except Exception:
            pass

    issued_date_str, issued_time_str = _fmt_datetime(getattr(receipt, "issued_at", None) if receipt else None)

    receipt_no = _receipt_number(payment, receipt)

    tenant_name = getattr(tenant, "name", None) or "-"
    tenant_phone = getattr(tenant, "phone", None) or "-"
    tenant_email = getattr(tenant, "email", None) or "-"
    tenant_id_no = getattr(tenant, "id_number", None) or "-"

    unit_label = getattr(unit, "number", None) or "-"
    property_name = getattr(property_, "name", None) or "-"
    property_code = getattr(property_, "property_code", None) or "-"
    property_address = getattr(property_, "address", None) or "-"

    landlord_name = getattr(landlord, "name", None) or "-"
    landlord_phone = getattr(landlord, "phone", None) or "-"

    manager_name = "-"
    if manager:
        manager_name = (
            getattr(manager, "company_name", None)
            or getattr(manager, "name", None)
            or "-"
        )

    lease_id = getattr(lease, "id", None) or getattr(payment, "lease_id", None) or "-"
    payment_id = getattr(payment, "id", None) or "-"

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x_left = 18 * mm
    x_right = w - 18 * mm
    y = h - 20 * mm

    def line_gap(mm_value: float = 6):
        nonlocal y
        y -= mm_value * mm

    def draw_label_value(label: str, value: str, x: float = x_left, label_width: float = 40 * mm):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(x + label_width, y, value)

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x_left, y, "PropSmart PMS")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(x_right, y, "OFFICIAL PAYMENT RECEIPT")
    line_gap(8)

    c.setStrokeColor(colors.lightgrey)
    c.line(x_left, y, x_right, y)
    line_gap(8)

    # Receipt summary
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_left, y, "Receipt Summary")
    line_gap(7)

    draw_label_value("Receipt No.:", receipt_no)
    line_gap()
    draw_label_value("Payment ID:", str(payment_id))
    line_gap()
    draw_label_value("Lease ID:", str(lease_id))
    line_gap()
    draw_label_value("Reference:", str(reference))
    line_gap()
    draw_label_value("Method:", str(payment_method))
    line_gap()
    draw_label_value("Status:", str(status).upper())
    line_gap()
    draw_label_value("Paid Date:", paid_date_str)
    line_gap()
    draw_label_value("Paid Time:", paid_time_str)
    line_gap()
    draw_label_value("Issued At:", f"{issued_date_str} {issued_time_str}")
    line_gap(10)

    # Property and parties
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_left, y, "Property / Parties")
    line_gap(7)

    draw_label_value("Property:", property_name)
    line_gap()
    draw_label_value("Property Code:", property_code)
    line_gap()
    draw_label_value("Address:", property_address)
    line_gap()
    draw_label_value("Unit:", unit_label)
    line_gap()
    draw_label_value("Tenant:", tenant_name)
    line_gap()
    draw_label_value("Tenant Phone:", tenant_phone)
    line_gap()
    draw_label_value("Tenant Email:", tenant_email)
    line_gap()
    draw_label_value("Tenant ID No.:", tenant_id_no)
    line_gap()
    draw_label_value("Landlord:", landlord_name)
    line_gap()
    draw_label_value("Landlord Phone:", landlord_phone)
    line_gap()
    draw_label_value("Manager/Agency:", manager_name)
    line_gap(10)

    # Total
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_left, y, "Payment Total")
    line_gap(7)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_left, y, f"Amount Received: {_fmt_money(amount)}")
    line_gap(10)

    # Allocations
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_left, y, "Allocation Breakdown")
    line_gap(8)

    table_x1 = x_left
    table_x2 = x_left + 95 * mm
    table_x3 = x_right
    row_h = 8 * mm

    c.setFillColor(colors.HexColor("#F3F4F6"))
    c.rect(table_x1, y - row_h + 2, table_x3 - table_x1, row_h, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(table_x1 + 4, y - 4 * mm, "Period")
    c.drawString(table_x2 + 4, y - 4 * mm, "Amount Applied")
    y -= row_h

    total_allocated = Decimal("0")
    c.setFont("Helvetica", 10)

    for row in allocations:
        if y < 35 * mm:
            c.showPage()
            y = h - 20 * mm

        period = str(row.get("period") or "-")
        applied = _safe_decimal(row.get("amount_applied", 0))
        total_allocated += applied

        c.setStrokeColor(colors.lightgrey)
        c.line(table_x1, y, table_x3, y)

        c.drawString(table_x1 + 4, y - 5 * mm, period)
        c.drawString(table_x2 + 4, y - 5 * mm, _fmt_money(applied))
        y -= row_h

    c.line(table_x1, y, table_x3, y)
    line_gap(4)

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(x_right, y, f"Allocated Total: {_fmt_money(total_allocated)}")
    line_gap(12)

    # Footer
    c.setStrokeColor(colors.lightgrey)
    c.line(x_left, 25 * mm, x_right, 25 * mm)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString(
        x_left,
        19 * mm,
        "Thank you. This receipt is system generated and valid without a signature.",
    )
    c.setFillColor(colors.black)

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()
    return pdf


def _authz_ok(
    current: dict,
    tenant: Optional[models.Tenant],
    property_: Optional[models.Property],
    landlord: Optional[models.Landlord],
) -> bool:
    role = current.get("role")
    uid = int(current.get("sub", 0) or 0)

    if role == "tenant":
        return bool(tenant and tenant.id == uid)

    if role == "landlord":
        return bool(property_ and landlord and landlord.id == uid)

    if role in {"admin", "super_admin", "property_manager", "manager"}:
        return True

    return False


@router.get("/receipt/{payment_id}/pdf")
@router.get("/receipt/{payment_id}.pdf")
def payment_receipt_pdf(
    payment_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    payment: Optional[models.Payment] = (
        db.query(models.Payment)
        .filter(models.Payment.id == payment_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    receipt = _ensure_receipt(db, payment)

    tenant: Optional[models.Tenant] = (
        db.query(models.Tenant)
        .filter(models.Tenant.id == payment.tenant_id)
        .first()
    )

    unit: Optional[models.Unit] = (
        db.query(models.Unit)
        .filter(models.Unit.id == payment.unit_id)
        .first()
    )

    lease: Optional[models.Lease] = (
        db.query(models.Lease)
        .filter(models.Lease.id == payment.lease_id)
        .first()
        if payment.lease_id
        else None
    )

    property_: Optional[models.Property] = (
        db.query(models.Property)
        .filter(models.Property.id == (unit.property_id if unit else 0))
        .first()
    )

    landlord: Optional[models.Landlord] = (
        db.query(models.Landlord)
        .filter(models.Landlord.id == (property_.landlord_id if property_ else 0))
        .first()
        if property_
        else None
    )

    manager = None
    if property_ and getattr(property_, "manager_id", None):
        try:
            manager = (
                db.query(models.PropertyManager)
                .filter(models.PropertyManager.id == property_.manager_id)
                .first()
            )
        except Exception:
            manager = None

    if not _authz_ok(current, tenant, property_, landlord):
        raise HTTPException(status_code=403, detail="Forbidden")

    # 1. Prefer saved PDF if it exists
    if receipt and getattr(receipt, "pdf_path", None):
        pdf_path = receipt.pdf_path
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf = f.read()

                filename = f"{receipt.receipt_number or f'receipt_{payment_id}'}.pdf"
                return Response(
                    content=pdf,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            except Exception:
                pass

    # 2. Fallback: generate live PDF from DB
    allocations = _get_allocations(db, payment, receipt)
    pdf = _build_pdf_bytes(
        payment=payment,
        receipt=receipt,
        tenant=tenant,
        unit=unit,
        lease=lease,
        property_=property_,
        landlord=landlord,
        manager=manager,
        allocations=allocations,
    )

    filename = f"{_receipt_number(payment, receipt)}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )