import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.security_models import PasswordResetOTP


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices("0123456789", k=length))


def invalidate_existing_otps(db: Session, email: str, purpose: str = "password_reset") -> None:
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == email,
        PasswordResetOTP.purpose == purpose,
        PasswordResetOTP.is_used == False,  # noqa: E712
    ).update({"is_used": True}, synchronize_session=False)
    db.flush()


def create_password_reset_otp(db: Session, email: str) -> PasswordResetOTP:
    invalidate_existing_otps(db, email, purpose="password_reset")

    otp = PasswordResetOTP(
        email=email,
        otp_code=generate_otp(),
        purpose="password_reset",
        expires_at=datetime.utcnow() + timedelta(
            minutes=settings.PASSWORD_RESET_OTP_EXPIRY_MINUTES
        ),
        is_used=False,
        attempts=0,
    )
    db.add(otp)
    db.flush()
    return otp


def get_valid_password_reset_otp(db: Session, email: str, otp_code: str) -> PasswordResetOTP | None:
    now = datetime.utcnow()
    return db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == email,
        PasswordResetOTP.otp_code == otp_code,
        PasswordResetOTP.purpose == "password_reset",
        PasswordResetOTP.is_used == False,  # noqa: E712
        PasswordResetOTP.expires_at > now,
    ).order_by(PasswordResetOTP.id.desc()).first()


def mark_otp_used(db: Session, otp: PasswordResetOTP) -> None:
    otp.is_used = True
    db.add(otp)
    db.flush()


def increment_otp_attempt(db: Session, otp: PasswordResetOTP) -> None:
    otp.attempts += 1
    db.add(otp)
    db.flush()