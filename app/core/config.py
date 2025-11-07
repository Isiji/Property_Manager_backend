# app/core/config.py
from functools import lru_cache
from typing import Optional, List
import json
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_origins(raw: Optional[str]) -> List[str]:
    """
    Accept both:
      - Comma-separated string:  "http://a.com, https://b.com"
      - JSON array string:       '["http://a.com","https://b.com"]'
      - Empty/None -> []
    Whitespace is trimmed, empties removed, duplicates de-duped (order kept).
    """
    if not raw:
        return []
    raw = raw.strip()

    # Try JSON first if it looks like JSON
    if raw.startswith("[") and raw.endswith("]"):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass  # fall back to comma split

    # Fallback: comma separated
    parts = [p.strip() for p in raw.split(",")]
    seen = set()
    out: List[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


class Settings(BaseSettings):
    # ─────────── DATABASE ───────────
    DATABASE_URL: str

    # ─────────── SECURITY ───────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # ─────────── SMS CONFIG ───────────
    SMS_PROVIDER: Optional[str] = None  # "twilio" | "africastalking" | "console"
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM: Optional[str] = None

    AT_API_KEY: Optional[str] = None
    AT_USERNAME: Optional[str] = None
    AT_FROM: Optional[str] = None

    SMS_ENABLED: bool = True
    EMAIL_ENABLED: bool = True

    # ─────────── MPESA (DARAJA) CONFIG ───────────
    DARAJA_BASE_URL: Optional[str] = None
    DARAJA_CONSUMER_KEY: Optional[str] = None
    DARAJA_CONSUMER_SECRET: Optional[str] = None

    # LNM (STK) specific
    DARAJA_LNM_SHORTCODE: Optional[str] = None           # e.g. 174379 (sandbox) or 600XXX
    DARAJA_LNM_PASSKEY: Optional[str] = None         # required for STK
    DARAJA_RESULT_URL: Optional[str] = None
    DARAJA_TIMEOUT_URL: Optional[str] = None
    DARAJA_CALLBACK_URL: Optional[str] = None        # for STK Push
    
    # (Only needed for B2C/B2B; keep for later)
    DARAJA_INITIATOR_NAME: Optional[str] = None
    DARAJA_INITIATOR_PASSWORD: Optional[str] = None
    DARAJA_SECURITY_CERT_PATH: Optional[str] = None

    # ─────────── EMAIL CONFIG ───────────
    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[int] = None
    EMAIL_USE_TLS: Optional[bool] = None
    EMAIL_HOST_USER: Optional[str] = None
    EMAIL_HOST_PASSWORD: Optional[str] = None

    # ─────────── CORS / FRONTEND ORIGINS ───────────
    # Read as plain string to avoid JSON decoding errors, then parse.
    FRONTEND_ORIGINS_RAW: Optional[str] = None

    # ─────────── GENERAL ───────────
    APP_NAME: str = "Property Manager"
    DEBUG: bool = True

    # pydantic-settings v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate extra vars in .env
    )

    # Derived property: final list of origins
    @property
    def CORS_ORIGINS(self) -> List[str]:
        defaults = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:63187",    # Flutter web dev (port varies)
            "http://127.0.0.1:63187",
        ]
        env_list = _parse_origins(self.FRONTEND_ORIGINS_RAW)
        # Merge env over defaults (dedupe, keep order)
        merged = []
        seen = set()
        for it in defaults + env_list:
            if it and it not in seen:
                seen.add(it)
                merged.append(it)
        return merged


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
