# app/services/notification_service.py
from app.crud import notification_crud
from sqlalchemy.orm import Session
from app.schemas.notification_schema import NotificationCreate

def send_notification(db: Session, payload: NotificationCreate):
    """
    Core function to send notification based on channel.
    """
    # 1️⃣ Always save in-app
    notif = notification_crud.create_notification(db, payload)

    # 2️⃣ Placeholder for email
    if payload.channel in ("email", "all"):
        send_email(payload)

    # 3️⃣ Placeholder for WhatsApp
    if payload.channel in ("whatsapp", "all"):
        send_whatsapp(payload)

    return notif


# =========================
# Placeholder Functions
# =========================

def send_email(payload: NotificationCreate):
    # TODO: Connect to SendGrid, SES, or any cheap email provider
    print(f"[Email] To user {payload.user_id}: {payload.title} - {payload.message}")

def send_whatsapp(payload: NotificationCreate):
    # TODO: Connect to Twilio or Africa's Talking
    print(f"[WhatsApp] To user {payload.user_id}: {payload.title} - {payload.message}")
