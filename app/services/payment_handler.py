# app/services/payment_handler.py
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from app import models
from app.models.receipt_model import PaymentReceipt
from app.services.receipt_service import build_receipt_pdf

try:
    from app.services.notification_engine import send_payment_notifications
except Exception:
    send_payment_notifications = None


def _serialize_allocations(payment: models.Payment) -> str:
    rows = []
    for a in getattr(payment, "allocations", []) or []:
        rows.append({
            "period": getattr(a, "period", None),
            "amount_applied": float(getattr(a, "amount_applied", 0) or 0),
        })
    return json.dumps(rows)


def _payment_notes_dict(payment: models.Payment) -> dict:
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


def handle_payment_success(db: Session, payment: models.Payment):
    existing_receipt = (
        db.query(PaymentReceipt)
        .filter(PaymentReceipt.payment_id == payment.id)
        .first()
    )
    if existing_receipt:
        return existing_receipt

    tenant = payment.tenant
    unit = payment.unit
    property_ = unit.property if unit else None
    landlord = property_.landlord if property_ else None
    manager = getattr(property_, "manager", None) if property_ else None

    _, pdf_path, receipt_number = build_receipt_pdf(
        payment=payment,
        tenant=tenant,
        unit=unit,
        property_=property_,
        landlord=landlord,
        manager=manager,
    )

    notes_dict = _payment_notes_dict(payment)

    receipt = PaymentReceipt(
        receipt_number=receipt_number,
        payment_id=payment.id,
        tenant_id=tenant.id if tenant else payment.tenant_id,
        unit_id=unit.id if unit else payment.unit_id,
        property_id=property_.id if property_ else 0,
        landlord_id=landlord.id if landlord else None,
        manager_id=manager.id if manager else None,
        amount=payment.amount,
        period=payment.period,
        allocations_json=_serialize_allocations(payment),
        payment_reference=payment.reference,
        payment_method=getattr(payment, "payment_method", None) or "M-Pesa",
        pdf_path=pdf_path,
    )

    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    if send_payment_notifications and tenant and property_:
        try:
            send_payment_notifications(
                db,
                tenant=tenant,
                landlord=landlord,
                manager=manager,
                payment=payment,
                property_=property_,
            )
        except Exception:
            pass

    return receipt