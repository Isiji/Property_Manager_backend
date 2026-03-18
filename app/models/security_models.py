from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.database import Base


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    otp_code = Column(String, nullable=False)
    purpose = Column(String, nullable=False, default="password_reset")
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, nullable=False, default=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)  # email | sms | whatsapp
    recipient = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)  # pending | sent | failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)