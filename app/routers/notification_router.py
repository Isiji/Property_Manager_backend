from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db, get_current_user
from app.schemas.notification_schema import NotificationCreate, NotificationOut
from app.crud import notification_crud as crud
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Existing explicit endpoints
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


# ----------------------------
# NEW: token-aware convenience
# ----------------------------
@router.get("/me", response_model=List[NotificationOut])
def my_notifications(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    user_id = int(current.get("sub", 0) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")
    return crud.list_notifications(db, user_id, limit=limit)

@router.get("/unread_count")
def my_unread_count(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    user_id = int(current.get("sub", 0) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"count": crud.unread_count(db, user_id)}

@router.post("/mark_all_read")
def my_mark_all_read(
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    user_id = int(current.get("sub", 0) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")
    changed = crud.mark_all_read(db, user_id)
    return {"updated": changed}
