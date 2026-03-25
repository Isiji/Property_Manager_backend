# app/services/receipt_service.py
from __future__ import annotations

import json
import os
import uuid
from io import BytesIO
from datetime import datetime
from typing import Optional, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


BASE_DIR = os.path.abspath(os.getcwd())
RECEIPT_DIR = os.path.join(BASE_DIR, "storage", "receipts")
os.makedirs(RECEIPT_DIR, exist_ok=True)


def generate_receipt_number() -> str:
    return f"RCPT-{uuid.uuid4().hex[:10].upper()}"


def _text_line(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    size: int = 11,
    bold: bool = False,
):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, text)


def _money(v: Any) -> str:
    try:
        return f"KES {float(v or 0):,.2f}"
    except Exception:
        return f"KES {v}"


def _safe(v: Any, fallback: str = "-") -> str:
    if v is None:
        return fallback
    s = str(v).strip()
    return s if s else fallback


def _notes_dict(payment) -> dict:
    raw = getattr(payment, "notes", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def _allocations(payment) -> list[dict]:
    rows = []
    for a in getattr(payment, "allocations", []) or []:
        rows.append({
            "period": getattr(a, "period", None),
            "amount_applied": float(getattr(a, "amount_applied", 0) or 0),
        })
    rows.sort(key=lambda x: str(x.get("period") or ""))
    return rows


def _pretty_month(period: str) -> str:
    try:
        y, m = period.split("-")
        dt_obj = datetime(int(y), int(m), 1)
        return dt_obj.strftime("%b %Y")
    except Exception:
        return period or "-"


def _periods_summary(payment) -> str:
    allocations = _allocations(payment)
    if allocations:
        periods = [_pretty_month(a["period"]) for a in allocations if a.get("period")]
        if periods:
            return ", ".join(periods)

    selected_raw = getattr(payment, "selected_periods_json", None)
    if selected_raw:
        try:
            decoded = json.loads(selected_raw)
            if isinstance(decoded, list):
                cleaned = [_pretty_month(str(p)) for p in decoded if str(p).strip()]
                if cleaned:
                    return ", ".join(cleaned)
        except Exception:
            pass

    return _pretty_month(getattr(payment, "period", None) or "-")


def _draw_wrapped_text(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    max_width: float,
    size: int = 10,
    bold: bool = False,
    leading: float = 5.5 * mm,
) -> float:
    font_name = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(font_name, size)

    words = str(text or "").split()
    if not words:
        c.drawString(x, y, "-")
        return y - leading

    line = ""
    current_y = y

    for word in words:
        trial = word if not line else f"{line} {word}"
        if c.stringWidth(trial, font_name, size) <= max_width:
            line = trial
        else:
            c.drawString(x, current_y, line)
            current_y -= leading
            line = word

    if line:
        c.drawString(x, current_y, line)
        current_y -= leading

    return current_y


def _ensure_space(c: canvas.Canvas, current_y: float, min_y: float = 20 * mm) -> float:
    if current_y < min_y:
        c.showPage()
        return A4[1] - 25 * mm
    return current_y


def build_receipt_pdf(
    payment,
    tenant,
    unit,
    property_,
    landlord: Optional[object] = None,
    manager: Optional[object] = None,
) -> tuple[bytes, str, str]:
    receipt_number = generate_receipt_number()

    file_name = f"{receipt_number}.pdf"
    file_path = os.path.join(RECEIPT_DIR, file_name)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    left = 20 * mm
    right = w - 20 * mm
    top = h - 25 * mm
    line = top

    notes = _notes_dict(payment)
    allocations = _allocations(payment)

    mpesa_ref = _safe(
        notes.get("mpesa_receipt_number") or getattr(payment, "reference", None)
    )
    mpesa_phone = _safe(notes.get("mpesa_phone_number"))
    mpesa_tx_time = _safe(notes.get("mpesa_transaction_date_iso"))
    merchant_request_id = _safe(
        notes.get("merchant_request_id") or getattr(payment, "merchant_request_id", None)
    )
    checkout_request_id = _safe(
        notes.get("checkout_request_id") or getattr(payment, "checkout_request_id", None)
    )
    payment_method = _safe(getattr(payment, "payment_method", None), "M-Pesa")
    issued_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Header
    _text_line(c, left, line, "PropSmart PMS", size=18, bold=True)
    line -= 8 * mm
    _text_line(c, left, line, "OFFICIAL PAYMENT RECEIPT", size=13, bold=True)
    line -= 10 * mm

    # Receipt meta
    _text_line(c, left, line, f"Receipt No: {receipt_number}", bold=True)
    line -= 6 * mm
    _text_line(c, left, line, f"Issued At: {issued_at}")
    line -= 10 * mm

    # Property section
    _text_line(c, left, line, "Property Details", size=12, bold=True)
    line -= 6 * mm
    _text_line(c, left, line, f"Property: {_safe(getattr(property_, 'name', None))}")
    line -= 6 * mm
    _text_line(c, left, line, f"Property Code: {_safe(getattr(property_, 'property_code', None))}")
    line -= 6 * mm
    line = _draw_wrapped_text(
        c,
        left,
        line,
        f"Address: {_safe(getattr(property_, 'address', None))}",
        max_width=right - left,
        size=11,
    )
    _text_line(c, left, line, f"Unit: {_safe(getattr(unit, 'number', None))}")
    line -= 10 * mm

    # Owner / Agency section
    line = _ensure_space(c, line)
    _text_line(c, left, line, "Owner / Agency", size=12, bold=True)
    line -= 6 * mm
    if landlord:
        _text_line(c, left, line, f"Landlord: {_safe(getattr(landlord, 'name', None))}")
        line -= 6 * mm
    if manager:
        manager_name = getattr(manager, "company_name", None) or getattr(manager, "name", None)
        _text_line(c, left, line, f"Agency / Manager: {_safe(manager_name)}")
        line -= 6 * mm
    line -= 4 * mm

    # Tenant section
    line = _ensure_space(c, line)
    _text_line(c, left, line, "Tenant Details", size=12, bold=True)
    line -= 6 * mm
    _text_line(c, left, line, f"Tenant: {_safe(getattr(tenant, 'name', None))}")
    line -= 6 * mm
    _text_line(c, left, line, f"Phone: {_safe(getattr(tenant, 'phone', None))}")
    line -= 6 * mm
    _text_line(c, left, line, f"Email: {_safe(getattr(tenant, 'email', None))}")
    line -= 6 * mm
    _text_line(c, left, line, f"ID Number: {_safe(getattr(tenant, 'id_number', None))}")
    line -= 10 * mm

    # Payment section
    line = _ensure_space(c, line)
    _text_line(c, left, line, "Payment Details", size=12, bold=True)
    line -= 6 * mm
    _text_line(c, left, line, f"Amount Paid: {_money(getattr(payment, 'amount', 0))}")
    line -= 6 * mm
    _text_line(c, left, line, f"Payment Method: {payment_method}")
    line -= 6 * mm
    _text_line(c, left, line, f"M-Pesa Ref: {mpesa_ref}")
    line -= 6 * mm
    _text_line(c, left, line, f"Paid Date: {_safe(payment.paid_date.isoformat() if getattr(payment, 'paid_date', None) else None)}")
    line -= 6 * mm
    _text_line(c, left, line, f"Rent Period(s): {_periods_summary(payment)}")
    line -= 10 * mm

    # M-Pesa details
    line = _ensure_space(c, line)
    _text_line(c, left, line, "M-Pesa Transaction Details", size=12, bold=True)
    line -= 6 * mm
    _text_line(c, left, line, f"Transaction Code: {mpesa_ref}")
    line -= 6 * mm
    _text_line(c, left, line, f"Phone Number: {mpesa_phone}")
    line -= 6 * mm
    _text_line(c, left, line, f"Transaction Time: {mpesa_tx_time}")
    line -= 6 * mm

    line = _draw_wrapped_text(
        c,
        left,
        line,
        f"Merchant Request ID: {merchant_request_id}",
        max_width=right - left,
        size=10,
    )
    line = _draw_wrapped_text(
        c,
        left,
        line,
        f"Checkout Request ID: {checkout_request_id}",
        max_width=right - left,
        size=10,
    )
    line -= 4 * mm

    # Allocation breakdown
    line = _ensure_space(c, line)
    _text_line(c, left, line, "Allocation Breakdown", size=12, bold=True)
    line -= 7 * mm

    if allocations:
        _text_line(c, left, line, "Period", size=11, bold=True)
        _text_line(c, right - 50 * mm, line, "Amount Applied", size=11, bold=True)
        line -= 5 * mm

        c.line(left, line, right, line)
        line -= 6 * mm

        for alloc in allocations:
            line = _ensure_space(c, line, min_y=30 * mm)
            period_label = _pretty_month(alloc.get("period") or "-")
            amount_label = _money(alloc.get("amount_applied") or 0)

            _text_line(c, left, line, period_label, size=10)
            _text_line(c, right - 50 * mm, line, amount_label, size=10)
            line -= 6 * mm
    else:
        _text_line(c, left, line, f"Single Period: {_safe(getattr(payment, 'period', None))}")
        line -= 6 * mm

    line -= 4 * mm

    # Footer
    line = _ensure_space(c, line)
    _text_line(c, left, line, "Thank you for your payment.", bold=True)
    line -= 6 * mm
    _text_line(
        c,
        left,
        line,
        "Generated by PropSmart PMS. This is a system-generated receipt.",
        size=9,
    )

    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    return pdf_bytes, file_path, receipt_number