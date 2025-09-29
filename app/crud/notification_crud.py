# app/crud/notification_crud.py
from sqlalchemy.orm import Session
from app.models.notification_model import Notification
from app.schemas.notification_schema import NotificationCreate

def create_notification(db: Session, payload: NotificationCreate):
    notif = Notification(**payload.dict())
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def list_notifications(db: Session, user_id: int):
    return db.query(Notification).filter(Notification.user_id == user_id).all()

def mark_as_read(db: Session, notif_id: int):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif
