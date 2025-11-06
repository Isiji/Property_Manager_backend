# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # ─────────── DATABASE ───────────
    DATABASE_URL: str

    # ─────────── SECURITY ───────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # ─────────── SMS CONFIG ───────────
    SMS_PROVIDER: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM: Optional[str] = None
    AT_API_KEY: Optional[str] = None
    AT_USERNAME: Optional[str] = None
    AT_FROM: Optional[str] = None

    SMS_ENABLED: bool = True
    EMAIL_ENABLED: bool = True

    # ─────────── MPESA (Daraja) ───────────
    DARAJA_BASE_URL: Optional[str] = None
    DARAJA_CONSUMER_KEY: Optional[str] = None
    DARAJA_CONSUMER_SECRET: Optional[str] = None

    # (B2C/B2B; not used for STK right now)
    DARAJA_SHORTCODE: Optional[str] = None
    DARAJA_INITIATOR_NAME: Optional[str] = None
    DARAJA_INITIATOR_PASSWORD: Optional[str] = None
    DARAJA_SECURITY_CERT_PATH: Optional[str] = None
    DARAJA_RESULT_URL: Optional[str] = None
    DARAJA_TIMEOUT_URL: Optional[str] = None

    # Lipa Na M-Pesa Online (STK Push)
    DARAJA_LNM_SHORTCODE: Optional[str] = None
    DARAJA_LNM_PASSKEY: Optional[str] = None
    DARAJA_CALLBACK_URL: Optional[str] = None

    # ─────────── EMAIL CONFIG ───────────
    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[int] = None
    EMAIL_USE_TLS: Optional[bool] = None
    EMAIL_HOST_USER: Optional[str] = None
    EMAIL_HOST_PASSWORD: Optional[str] = None

    # ─────────── GENERAL ───────────
    APP_NAME: str = "Property Manager"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
