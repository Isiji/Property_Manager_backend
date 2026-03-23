from sqlalchemy.orm import Session

from app.services.notification_service import (
    notify_email,
    notify_sms,
    notify_whatsapp,
)


def send_payment_notifications(
    db: Session,
    *,
    tenant,
    landlord,
    manager,
    payment,
    property_,
):
    message = f"Payment of KES {payment.amount} received for {property_.name} ({payment.period})"

    # Tenant
    if tenant.email:
        notify_email(
            db,
            to_email=tenant.email,
            subject="Payment Received",
            message=message,
            event_type="rent_paid",
        )

    if tenant.phone:
        notify_sms(
            db,
            to_phone=tenant.phone,
            message=message,
            event_type="rent_paid",
        )

    # Landlord
    if landlord and landlord.email:
        notify_email(
            db,
            to_email=landlord.email,
            subject="Tenant Payment Received",
            message=message,
            event_type="rent_paid",
        )

    # Manager / Agency
    if manager and manager.email:
        notify_email(
            db,
            to_email=manager.email,
            subject="Payment Received",
            message=message,
            event_type="rent_paid",
        )