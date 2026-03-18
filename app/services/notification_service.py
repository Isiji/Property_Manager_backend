from datetime import datetime
from sqlalchemy.orm import Session

from app.models.security_models import NotificationLog
from app.services.email_service import send_email
from app.services.sms_service import send_sms, send_whatsapp


def _log_notification(
    db: Session,
    event_type: str,
    channel: str,
    recipient: str,
    message: str,
    subject: str | None = None,
    status: str = "pending",
    error_message: str | None = None,
):
    log = NotificationLog(
        event_type=event_type,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message,
        status=status,
        error_message=error_message,
        sent_at=datetime.utcnow() if status == "sent" else None,
    )
    db.add(log)
    db.flush()
    return log


def notify_email(
    db: Session,
    *,
    to_email: str,
    subject: str,
    message: str,
    event_type: str,
    html_message: str | None = None,
):
    log = _log_notification(
        db=db,
        event_type=event_type,
        channel="email",
        recipient=to_email,
        subject=subject,
        message=message,
    )

    try:
        send_email(to_email=to_email, subject=subject, body=message, html_body=html_message)
        log.status = "sent"
        log.sent_at = datetime.utcnow()
    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)

    db.add(log)
    db.flush()
    return log


def notify_sms(
    db: Session,
    *,
    to_phone: str,
    message: str,
    event_type: str,
):
    log = _log_notification(
        db=db,
        event_type=event_type,
        channel="sms",
        recipient=to_phone,
        message=message,
    )

    try:
        send_sms(to_phone=to_phone, message=message)
        log.status = "sent"
        log.sent_at = datetime.utcnow()
    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)

    db.add(log)
    db.flush()
    return log


def notify_whatsapp(
    db: Session,
    *,
    to_phone: str,
    message: str,
    event_type: str,
):
    log = _log_notification(
        db=db,
        event_type=event_type,
        channel="whatsapp",
        recipient=to_phone,
        message=message,
    )

    try:
        send_whatsapp(to_phone=to_phone, message=message)
        log.status = "sent"
        log.sent_at = datetime.utcnow()
    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)

    db.add(log)
    db.flush()
    return log