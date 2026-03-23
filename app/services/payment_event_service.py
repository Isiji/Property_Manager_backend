from sqlalchemy.orm import Session

from app import models
from app.models.receipt_model import PaymentReceipt
from app.services.receipt_service import build_receipt_pdf
from app.services.notification_engine import send_payment_notifications


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
    property_ = unit.property
    landlord = property_.landlord
    manager = property_.manager

    pdf_bytes, pdf_path, receipt_number = build_receipt_pdf(
        payment,
        tenant,
        unit,
        property_,
        landlord,
        manager,
    )

    receipt = PaymentReceipt(
        receipt_number=receipt_number,
        payment_id=payment.id,
        tenant_id=tenant.id,
        unit_id=unit.id,
        property_id=property_.id,
        landlord_id=landlord.id if landlord else None,
        manager_id=manager.id if manager else None,
        amount=payment.amount,
        period=payment.period,
        payment_reference=payment.reference,
        payment_method="M-Pesa",
        pdf_path=pdf_path,
    )

    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    send_payment_notifications(
        db,
        tenant=tenant,
        landlord=landlord,
        manager=manager,
        payment=payment,
        property_=property_,
    )

    return receipt