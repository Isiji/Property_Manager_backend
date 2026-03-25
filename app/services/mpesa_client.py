# app/services/mpesa_client.py
from __future__ import annotations

from app.services.daraja_service import DarajaClient, daraja_client


class MpesaClient(DarajaClient):
    """
    Backward-compatible alias.
    Prefer importing from app.services.daraja_service instead.
    """
    pass


mpesa_client = daraja_client