# app/crud/notification_crud.py
from sqlalchemy.orm import Session
from datetime import datetime
from app import models
from app.schemas.notification_schema import NotificationCreate

def create_notification(db: Session, payload: NotificationCreate) -> models.Notification:
    data = payload.model_dump()

    # Safety net: ensure user_type is present (DB is NOT NULL)
    if not data.get("user_type"):
        data["user_type"] = "system"

    notif = models.Notification(
        user_id=data["user_id"],
        user_type=data["user_type"],
        title=data["title"],
        message=data["message"],
        channel=data.get("channel", "inapp"),
        is_read=False,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def list_notifications(db: Session, user_id: int, limit: int = 50):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
        .limit(limit)
        .all()
    )

def mark_as_read(db: Session, notif_id: int):
    n = db.query(models.Notification).filter(models.Notification.id == notif_id).first()
    if not n:
        return None
    n.is_read = True
    db.commit()
    db.refresh(n)
    return n

def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, models.Notification.is_read == False)  # noqa: E712
        .count()
    )

def mark_all_read(db: Session, user_id: int) -> int:
    q = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, models.Notification.is_read == False)  # noqa: E712
    )
    count = q.count()
    for n in q.all():
        n.is_read = True
    db.commit()
    return count
