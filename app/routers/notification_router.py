# app/routers/notification_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.notification_schema import NotificationCreate, NotificationOut
from app.crud import notification_crud as crud
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/", response_model=NotificationOut)
def send_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    return notification_service.send_notification(db, payload)
@router.get("/{user_id}", response_model=List[NotificationOut])
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    return crud.list_notifications(db, user_id)

@router.put("/{notif_id}/read", response_model=NotificationOut)
def read_notification(notif_id: int, db: Session = Depends(get_db)):
    notif = crud.mark_as_read(db, notif_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif
