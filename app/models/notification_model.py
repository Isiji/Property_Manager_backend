# app/models/notification_model.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # ID of the user (tenant, landlord, admin, manager)
    user_type = Column(String, nullable=False)  # 'tenant', 'landlord', 'admin', 'manager'
    
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    channel = Column(String, default="in_app")  # in_app, email, sms, whatsapp
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
