# app/services/receipt_service.py
from __future__ import annotations
from io import BytesIO
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app import models

def _text_line(c: canvas.Canvas, x: float, y: float, text: str, size=11, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, text)

def build_receipt_pdf(payment: models.Payment,
                      tenant: models.Tenant,
                      unit: models.Unit,
                      property_: models.Property,
                      landlord: Optional[models.Landlord]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    left = 20 * mm
    top = h - 25 * mm
    line = top

    # Header
    _text_line(c, left, line, property_.name or "Property", size=16, bold=True); line -= 8*mm
    _text_line(c, left, line, f"Address: {property_.address or '-'}"); line -= 6*mm
    if landlord:
      _text_line(c, left, line, f"Landlord: {landlord.name} • {landlord.phone or ''}"); line -= 8*mm

    _text_line(c, left, line, "PAYMENT RECEIPT", size=14, bold=True); line -= 10*mm

    # Payment summary
    _text_line(c, left, line, f"Receipt No: {payment.reference or 'N/A'}", bold=True); line -= 6*mm
    _text_line(c, left, line, f"Date: {(payment.paid_date or payment.created_at.date()).isoformat()}"); line -= 6*mm
    _text_line(c, left, line, f"Period: {payment.period}"); line -= 6*mm
    _text_line(c, left, line, f"Amount: KES {payment.amount}"); line -= 8*mm

    # Tenant / Unit
    _text_line(c, left, line, f"Tenant: {tenant.name} • {tenant.phone}"); line -= 6*mm
    _text_line(c, left, line, f"Unit: {unit.number} • Property Code: {property_.property_code or '-'}"); line -= 10*mm

    # Footer / thanks
    _text_line(c, left, line, "Thank you for your payment.", bold=True); line -= 6*mm
    _text_line(c, left, line, f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z", size=9)

    c.showPage()
    c.save()
    return buf.getvalue()
