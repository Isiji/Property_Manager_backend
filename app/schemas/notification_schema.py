# app/schemas/notification_schema.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class NotificationCreate(BaseModel):
    user_id: int
    user_type: str       # ✅ required: e.g. "landlord", "property_manager", "tenant", "admin"
    title: str
    message: str
    channel: str = "inapp"  # inapp | email | whatsapp | all

class NotificationOut(BaseModel):
    id: int
    user_id: int
    user_type: str
    title: str
    message: str
    channel: str
    is_read: bool
    created_at: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)
