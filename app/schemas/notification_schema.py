# app/schemas/notification_schema.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class NotificationBase(BaseModel):
    user_id: int
    title: str
    message: str
    channel: Optional[str] = "in_app"

class NotificationCreate(NotificationBase):
    pass

class NotificationOut(NotificationBase):
    id: int
    is_read: bool
    created_at: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)
