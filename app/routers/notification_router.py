from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import or_
from app.dependencies import get_db, get_current_user
from app.schemas.notification_schema import NotificationCreate, NotificationOut
from app.crud import notification_crud as crud
from app import models
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/", response_model=NotificationOut)
def send_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    return notification_service.send_notification(db, payload)

@router.get("", response_model=List[NotificationOut])
def list_my_notifications(
    db: Session = Depends(get_db),
    current = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = Query(None, pattern="^(maintenance|payment|system)$"),
):
    uid = int((current or {}).get("sub", 0) or 0)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")

    q = db.query(models.Notification).filter(models.Notification.user_id == uid)

    # heuristic type filter (can upgrade later by adding a 'category' column)
    if type == "maintenance":
        q = q.filter(or_(
            models.Notification.title.ilike("%maint%"),
            models.Notification.message.ilike("%maint%")
        ))
    elif type == "payment":
        q = q.filter(or_(
            models.Notification.title.ilike("%pay%"),
            models.Notification.message.ilike("%rent%")
        ))
    elif type == "system":
        q = q.filter(~or_(
            models.Notification.title.ilike("%maint%"),
            models.Notification.message.ilike("%maint%"),
            models.Notification.title.ilike("%pay%"),
            models.Notification.message.ilike("%rent%"),
        ))

    return q.order_by(models.Notification.created_at.desc()).limit(limit).all()

@router.get("/unread_count")
def unread_count(db: Session = Depends(get_db), current = Depends(get_current_user)):
    uid = int((current or {}).get("sub", 0) or 0)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"count": crud.unread_count(db, uid)}

@router.post("/mark_all_read")
def mark_all_read(db: Session = Depends(get_db), current = Depends(get_current_user)):
    uid = int((current or {}).get("sub", 0) or 0)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    n = crud.mark_all_read(db, uid)
    return {"marked": n}

@router.put("/{notif_id}/read", response_model=NotificationOut)
def mark_one_read(notif_id: int, db: Session = Depends(get_db), current = Depends(get_current_user)):
    notif = crud.mark_as_read(db, notif_id)
    if not notif or int(notif.user_id) != int((current or {}).get("sub", 0) or 0):
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif
