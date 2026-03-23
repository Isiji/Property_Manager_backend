from __future__ import annotations

import base64
import datetime as dt
from typing import Any, Dict

import requests
from fastapi import HTTPException

from app.core.config import settings


class DarajaClient:
    """
    M-Pesa Daraja Client (STK Push)
    Production-ready version.

    Requirements in .env:
    - DARAJA_BASE_URL
    - DARAJA_CONSUMER_KEY
    - DARAJA_CONSUMER_SECRET
    - DARAJA_LNM_SHORTCODE
    - DARAJA_LNM_PASSKEY
    - DARAJA_CALLBACK_URL
    """

    def __init__(self) -> None:
        self.base = settings.DARAJA_BASE_URL.rstrip("/")
        self.consumer_key = settings.DARAJA_CONSUMER_KEY
        self.consumer_secret = settings.DARAJA_CONSUMER_SECRET
        self.shortcode = settings.DARAJA_LNM_SHORTCODE
        self.passkey = settings.DARAJA_LNM_PASSKEY
        self.callback_url = settings.DARAJA_CALLBACK_URL

        if not all([
            self.base,
            self.consumer_key,
            self.consumer_secret,
            self.shortcode,
            self.passkey,
            self.callback_url,
        ]):
            raise RuntimeError("Daraja config is incomplete")

    # -------------------------
    # AUTH
    # -------------------------
    def _access_token(self) -> str:
        url = f"{self.base}/oauth/v1/generate?grant_type=client_credentials"

        response = requests.get(
            url,
            auth=(self.consumer_key, self.consumer_secret),
            timeout=20
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Daraja OAuth failed: {response.text}"
            )

        data = response.json()
        token = data.get("access_token")

        if not token:
            raise HTTPException(
                status_code=502,
                detail="Missing access_token from Daraja"
            )

        return token

    # -------------------------
    # HELPERS
    # -------------------------
    @staticmethod
    def _timestamp() -> str:
        return dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def _password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")

    # -------------------------
    # STK PUSH
    # -------------------------
    def initiate_stk_push(
        self,
        *,
        phone: str,
        amount: int | float,
        account_ref: str,
        description: str,
    ) -> Dict[str, Any]:

        timestamp = self._timestamp()
        password = self._password(timestamp)
        token = self._access_token()

        url = f"{self.base}/mpesa/stkpush/v1/processrequest"

        payload = {
            "BusinessShortCode": int(self.shortcode),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": int(phone),
            "PartyB": int(self.shortcode),
            "PhoneNumber": int(phone),
            "CallBackURL": self.callback_url,
            "AccountReference": account_ref[:12],
            "TransactionDesc": description[:60],
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )

        data = response.json() if response.content else {}

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={"daraja_error": data}
            )

        return data


# Singleton instance
daraja_client = DarajaClient()