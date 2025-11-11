# app/routers/notification_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dependencies import get_db, get_current_user
from app.schemas.notification_schema import NotificationCreate, NotificationOut
from app.crud import notification_crud as crud
from app import models

router = APIRouter(prefix="/notifications", tags=["Notifications"])

def _current_user_row(db: Session, current: dict) -> tuple[int, str]:
    role = (current.get("role") or "").lower()
    sub = int(current.get("sub") or 0)
    if sub <= 0 or role not in {"tenant","landlord","property_manager","admin"}:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Admins get their own inbox too; “system” is used only when sender is system
    return sub, role

@router.post("/", response_model=NotificationOut)
def send_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    # Service already guards user_type
    return crud.create_notification(db, payload)

@router.get("", response_model=List[NotificationOut])  # ← list MY notifications
def list_my_notifications(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    user_id, _ = _current_user_row(db, current)
    return crud.list_notifications(db, user_id=user_id, limit=limit)

@router.get("/unread_count")
def my_unread_count(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    user_id, _ = _current_user_row(db, current)
    return {"count": crud.unread_count(db, user_id)}

@router.post("/mark_all_read")
def my_mark_all_read(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    user_id, _ = _current_user_row(db, current)
    n = crud.mark_all_read(db, user_id)
    return {"ok": True, "marked": n}

@router.put("/{notif_id}/read", response_model=NotificationOut)
def read_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    # Optional: enforce ownership
    n = db.query(models.Notification).filter(models.Notification.id == notif_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    user_id, _ = _current_user_row(db, current)
    if n.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    n = crud.mark_as_read(db, notif_id)
    return n
